'''
@Reviewer: Abdelaziz Neamatallah
@Date: 25.12.25
@Description: Trying to understand how to use our own pcap files with the parsing function.

- This file basically does the following:
    1. read pcap
    2. extract raw protocol bytes per packet
    3. match requests and responses based on TCP seq/ack numbers
    4. write to CSV file with optional context length and timestamp inclusion
'''
#! for fixing the time issue
from datetime import datetime


# library for parsing from cmd
import argparse

# utility library used by PyShark for async operations
import asyncio

# Explicit types for better code clarity
from typing import Any, Dict

# used for file operations
import os

# used for creating csv files from dataframes.
import pandas as pd

# # wrapper for tshark to parse pcap files
import pyshark

# PyShark packet type
from pyshark.packet.packet import Packet

# for progress bars viewing
from tqdm import tqdm

# importing pathes.
from src.cfg import DATASET_DUMPS,OUTPUTS_DIR
DATASET_PARSED_Custom =f"{OUTPUTS_DIR}/datasets/parsed_custom" #! I created this for our custom parsed datasets.

SOURCE_TEXT = "source_text"
TARGET_TEXT = "target_text"


def parse_with_file(protocol: str, capture_layer: str, port: int, pcap: str, csv: str, context_length: int, has_time: bool, experiment: str):
    '''
        This function parses a pcap file given the protocol, port, and other parameters.
        Input:
            protocol: Protocol to filter (e.g., "mbtcp", "s7comm").
            capture_layer: Layer to decode as (e.g., "tpkt", "mbtcp").
            port: Port number to filter packets.
            pcap: Name of the pcap file (without .pcap extension).
            csv: Output CSV filename (without .csv extension).
            context_length: Number of previous packets to include as context.
            has_time: Whether to include timestamps in the output.
            experiment: Experiment name for directory structure.
    '''

    '''
    asyncio is used here to set up a new event loop for PyShark's FileCapture.
    async event loop is core scheduler in python asynchrounous runtime.
    It is a single-threaded loop that repeatedly waits for I/O and then dispatches callbacks or resumes async coroutines when those events are ready instead
    of blocking the entire program while waiting for I/O operations to complete.
    This happens in this code due to the fact that pyshark.FileCapture is built on top of asyncio to handle packet capturing and processing asynchronously.
    1. We create a new event loop using asyncio.new_event_loop().
    2. We set this new loop as the current event loop for the current thread using asyncio.set_event_loop().
    This ensures that when pyshark.FileCapture is used, it operates within the context of this newly created event loop, allowing it to function correctly in an asynchronous manner.
    3. Finally, we create a FileCapture object from pyshark, specifying the pcap file and various options for parsing.
    4. We then pass this FileCapture object to the __parse function to process the packets.

    '''
    print('Starting parse_with_file...')
    asyncio.set_event_loop(asyncio.new_event_loop())

    # Create a FileCapture object to read the pcap file with specified filters and decoding options
    '''
        - Creates a capturer reader over the {pcap}.pcap exist in DATASET_DUMPS folder. (This should be our own pcap files).
        - include_raw=True: This option tells PyShark to include the raw packet data in the capture. This is essential for extracting the raw protocol bytes later on.
        - display_filter=f'{protocol}': This filter ensures that only packets matching the specified protocol are processed.
        - decode_as={f'tcp.port=={port}': f'{capture_layer}'}: This option tells PyShark to decode packets on the specified TCP port as the given capture layer (e.g., 'mbtcp' for modbus).



    '''
    print(f"Reading pcap file: {DATASET_DUMPS}/{pcap}.pcap")
    cap = pyshark.FileCapture(f"{DATASET_DUMPS}/{pcap}.pcap", use_json=True, include_raw=True,
                              display_filter=f'{protocol}',
                              decode_as={f'tcp.port=={port}': f'{capture_layer}'})

    # calls the real parsing function
    __parse(protocol, port, cap, csv, context_length, has_time, experiment)


def parse_without_file(protocol: str, port: int, cap, csv_filename: str, context_length: int, has_time: bool, experiment: str):
    __parse(protocol, port, cap, csv_filename, context_length, has_time, experiment)


def __parse(protocol: str, port: int, cap, csv_filename: str, context_length: int, has_time: bool, experiment: str):
    '''
        This is the core function that does the parsing of packets from the given capture object.
    Input:
        protocol: Protocol to filter (e.g., "mbtcp", "s7comm").
        port: Port number to filter packets.
        cap: PyShark FileCapture object containing the packets.
        csv_filename: Output CSV filename (without .csv extension).
        context_length: Number of previous packets to include as context.
        has_time: Whether to include timestamps in the output.
        experiment: Experiment name for directory structure.
    Output:
        Writes a CSV file with parsed request-response pairs.
    '''
    print('Starting __parse...')

    # containers for source and target texts
    dataset_dict = {SOURCE_TEXT: [], TARGET_TEXT: []}

    # Two hash maps used to match requests and responses based on TCP seq/ack numbers
    request_packets: Dict[int, Any] = {}
    response_packets: Dict[int, Any] = {}

    # PyShark packet
    packet: Packet

    # Decide which row field to extract based on protocol.
    # Important detail: these strings are later passed into eval(), so they must refer to valid packet attributes.
    if protocol == "s7comm":
        eval_str = ["packet.tpkt_raw.value", "packet.cotp_raw.value", f"packet.{protocol}_raw.value"]
    else:
        eval_str = [f"packet.{protocol}_raw.value"] # mbtcp


    # Time tracking variables
    offset = 0 # accumulates time delts between packets
    prev_time = 0 # tracks the previous packet timestamp

    # iterates packets and collect requests and responses
    print('Iterating over packets...')
    max_iter = 1000 # read it from cmd later
    for index, packet in tqdm(enumerate(cap)):
        if index >= max_iter:
            print(f"Reached max iteration limit of {max_iter}. Stopping parse.")
            break
        # builds a list of raw hex strings for evaluation strings (mbtcp or tpkt, cotp, s7comm)
        fragments = []
        for item in eval_str: # for mbtcp, this loop runs once; for s7comm, it runs three times to get tpkt, cotp, and s7comm layers
            fragments.append(eval(item))
        the_value = ''.join(fragments) # concatenate all fragments into a single string


        # validate and compute timing.
        if packet.sniff_timestamp is None:
            raise ValueError("No timestamp")

        #! This line is causing error on WDT dataset, because timestamp is string in different format:
        #! ValueError: could not convert string to float: '2021-04-09T16:23:28.385003000Z'
        # the_time: float = float(packet.sniff_timestamp) # convert timestamp to float seconds

        #! My fix:
        ts = packet.sniff_timestamp

        if isinstance(ts, (int, float)):
            the_time = float(ts)
        else:
            # ts example: 2021-04-09T16:23:28.385003000Z
            ts = ts.replace("Z", "")

            # cut nanoseconds -> keep microseconds (6 digits)
            if "." in ts:
                date_part, frac = ts.split(".")
                frac = frac[:6]  # keep only microseconds
                ts = f"{date_part}.{frac}"

            the_time = datetime.fromisoformat(ts).timestamp()

        if index == 0: # initialize prev_time on first packet
            prev_time = the_time

        offset += the_time - prev_time

        prev_time = the_time

        # optionally attach time only for requests
        if has_time and int(packet.tcp.dstport) == port:
            the_value = {"packet": the_value, "offset": offset}

        '''
        # classify packet as request or response based on TCP ports and store in corresponding hash map
        # This is the main logic for mapping.
        # if dst port is 502, then this is from the client to the server as a request.
        # otherwise, it is from server to client as a response.
        # What this is trying to do:
            They want a shared “transaction id” between request and response.

            They approximate it using TCP sequencing:

            Response seq often corresponds to the request’s ack (not always perfect, but often lines up).

            ack_raw[-1] and seq_raw[-1] are a bit sketchy:

            ack_raw is typically a bytes-like list/field; taking [-1] means “last element”, not “full ack number”.

            If ack_raw/seq_raw are not what you think, the matching becomes garbage and you’ll get a lot of “Ignored”.
        #So this code works best when pyshark exposes these fields in a way that [-1] yields a stable integer token, and when traffic is simple request-response without fragmentation/retransmits.
        # '''
        if int(packet.tcp.dstport) == port:
            request_packets[int(packet.tcp.ack_raw[-1])] = the_value
        else:
            response_packets[int(packet.tcp.seq_raw[-1])] = the_value

    # Second pass: join requests and responses based on TID.
    '''
        Iterate over every stored request.
        Looks up response with the same tid.
            If found, appends to dataset_dict.
            If not found, prints "Ignored: {tid}".
        If matching fails then the output may become empty or incomplete.
    '''
    print('Matching requests and responses...')
    for tid, entry in tqdm(request_packets.items()):
        try:
            dataset_dict[TARGET_TEXT].append(response_packets[tid])
            dataset_dict[SOURCE_TEXT].append(entry)
        except:
            print(f"Ignored: {tid}")

    # Convert to DataFrame for easier CSV writing
    dataset_df = pd.DataFrame(dataset_dict)

    # Ensure output directory exists
    os.makedirs(f"{DATASET_PARSED_Custom}/{experiment}", exist_ok=True)

    # Write to CSV with context length or time if specified
    print('Writing to CSV...')
    if context_length > 0:
        # Write CSV with context length
        with open(f"{DATASET_PARSED_Custom}/{experiment}/{csv_filename}.csv", "w") as csv_context:
            csv_context.write(f"{SOURCE_TEXT},{TARGET_TEXT}\n")
            for i in range(0, len(dataset_df) - context_length, context_length + 1):
                # write context_length previous packets as context
                for j in range(0, context_length):
                    csv_context.write(f"{dataset_df[SOURCE_TEXT][i + j]}:{dataset_df[TARGET_TEXT][i + j]}|")
                csv_context.write(f"{dataset_df[SOURCE_TEXT][i + context_length]}:,{dataset_df[TARGET_TEXT][i + context_length]}")
                csv_context.write("\n")
    else:
        # if no context is needed but time is needed
        if has_time:
            with open(f"{DATASET_PARSED_Custom}/{experiment}/{csv_filename}.csv", "w") as csv_context:
                csv_context.write(f"{SOURCE_TEXT},{TARGET_TEXT}\n")
                for i in range(0, len(dataset_df)):
                    csv_context.write(f"{'%.2f' % (dataset_df[SOURCE_TEXT][i]['offset'])}|{dataset_df[SOURCE_TEXT][i]['packet']}:,{dataset_df[TARGET_TEXT][i]}\n")
        # if no context and no time
        else:
            dataset_df.to_csv(f"{DATASET_PARSED_Custom}/{experiment}/{csv_filename}.csv", index=False)


def main():
    '''
        This is the function that I was looking for, which allows me directly parse pcap files.
        Usage example:
            -  python -m src.dataset_generation.parse -pcap attack_1 -csv wdt_attack_1 -p 502 -layer mbtcp -pr mbtcp -clen 1 -exp wdt_custom_attack_1
                - has_time: False
            -  python -m src.dataset_generation.parse -pcap attack_1 -csv wdt_attack_1 -p 502 -layer mbtcp -pr mbtcp -clen 1 -exp wdt_custom_attack_1 -t
                - has_time: True
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('-pcap', default="mbtcp-testbed-sp65-c1-s3200", required=False) # input pcap file name without .pcap
    parser.add_argument('-csv', default="mbtcp-testbed-sp65-c1-s3200", required=False) # output csv file name without .csv
    parser.add_argument('-p', default="502", type=int, required=False) # port number
    parser.add_argument('-layer', default="mbtcp", required=False) # capture layer, e.g., tpkt
    parser.add_argument('-pr', default="mbtcp", required=False) # protocol, e.g., s7comm
    parser.add_argument('-clen', default=0, type= int, required=False) # context length
    parser.add_argument('-t', action="store_true", required=False) # whether to include time
    parser.add_argument('-exp', default="mbtcp-testbed.json", required=False) # experiment name
    args = parser.parse_args()


    pcap = args.pcap
    csv = args.csv
    port = args.p
    capture_layer = args.layer
    protocol = args.pr
    context_length = args.clen
    has_time = args.t
    experiment = args.exp

    print(f"has_time: {has_time}")

    if has_time and context_length > 0:
        raise ValueError("Cannot have time and context length at the same time")

    parse_with_file(protocol, capture_layer, port, pcap, csv, context_length, has_time, experiment)


if __name__ == '__main__':
    main()
