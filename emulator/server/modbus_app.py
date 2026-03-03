'''
@ Reviewer: Abdelaziz Neamatallah
@ Date: 09.02.2026
@ Description: Reviewing this script to understand how does modbus container work.
'''



import asyncio
import json
import os
import socketserver
from datetime import datetime

import torch
from beanie import init_beanie, WriteRules
from motor.motor_asyncio import AsyncIOMotorClient
from transformers import ByT5Tokenizer, T5ForConditionalGeneration

from model.modbus.client import Client
from model.modbus.request import Request
from cfg import PROJECT_ROOT_DIR
from finetune.custom_lightning.byt5_lightning_module import Byt5LightningModule
from finetune.model.finetuner_model import FinetunerModel
from utilities.logger import TheLogger


# creating a logger component to log all modbus activities.
logger = TheLogger("modbus_server", f"{PROJECT_ROOT_DIR}/logs")


# check if there is an existing gpu
if torch.cuda.is_available():
    device = torch.device("cuda")
    logger.info("CUDA is available. Using GPU.")
else:
    device = torch.device("cpu")
    logger.info("CUDA is not available. Using CPU.")


# creating a threaded TCP server to handle multiple clients concurrently.
class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


# load the trained model.
def load_model(finetuner_model: FinetunerModel):
    logger.info("Loading model...")
    tokenizer = ByT5Tokenizer.from_pretrained(finetuner_model.base_model_id())
    # model_orig = T5ForConditionalGeneration.from_pretrained(finetuner_model.base_model_id(), device_map="cuda")
    model_orig = T5ForConditionalGeneration.from_pretrained(finetuner_model.base_model_id(), device_map="cpu")
    model = Byt5LightningModule.load_from_checkpoint(
        checkpoint_path=f"{finetuner_model.experiment_instance_last_result_path}",
        finetuner_model=finetuner_model,
        tokenizer=tokenizer,
        model=model_orig,
        test_dataset=None,
        trust_remote_code=True,
        # device_map="cuda", #! changing it to cpu, because this vm does not contain gpu
        device_map="cpu", #! changing it to cpu, because this vm does not contain gpu
    )
    logger.info("Loading model... Done.")
    model.eval()
    return model, tokenizer


# one instance per TCP connection: this is the main handler logic
class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    # read experiment configuration from the provided path in the environment variable and initialize the finetuner model and load the trained model.
    with open(f"/app/{os.environ['EXPERIMENT_PATH']}", "r") as cfg:
        config = cfg.read()
        config = json.loads(config)

    # create experiment descriptor
    finetuner_model = FinetunerModel(experiment=os.environ['EXPERIMENT'], **config)

    # finds the correct trained run directory.
    finetuner_model.start_datetime = os.listdir(f"{finetuner_model.experiment_dataset_result_path}")[0]

    # load the trained model.
    model, tokenizer = load_model(finetuner_model)

    # handle incoming requests, generate responses using the model, and log all activities.
    def handle(self):
        asyncio.run(self.handle_async())

    async def handle_async(self):
        # receive raw tcp bytes from the attacker
        incoming_raw = self.request.recv(1024)
        # extract client IP and port for logging and database storage.
        client_ip = self.client_address[0]
        client_port = self.client_address[1]


        # convert the incoming raw bytes to a hexadecimal string for better readability and logging. If conversion fails, log the error and use the raw bytes as a string.
        try:
            incoming_str = ''.join(['{:02x}'.format(byte) for byte in incoming_raw])
        except:
            logger.error(f"IP: {client_ip}:{client_port} - Error: {incoming_raw}")
            incoming_str = str(incoming_raw)

        # log the incoming request details, including the client IP, port, raw bytes, and the converted string.
        logger.info(f"IP: {client_ip}:{client_port} - Incoming String: {incoming_str}, Incoming Raw: {incoming_raw}")

        # check if the client already exists in the database using the client IP. If not, create a new client entry. Then, create a new request entry for this client, generate a response using the model, and save all details to the database.
        client = await Client.find(Client.ip == client_ip).first_or_none()
        if client is None:
            # if not, create a new client entry in the database with the client's IP address.
            client = Client(ip=client_ip)

        # stores the incoming request details in the database, including the client ID, request string, and client port. Then, it generates a response using the model, converts it to raw bytes, and sends it back to the client. Finally, it logs the outgoing response details and saves everything to the database.
        client_request = Request(client=str(client.id), request=incoming_str, client_port=client_port)

        # the llm inference step: generate the outgoing response string based on the incoming request string using the loaded model. If the model fails to generate a valid hexadecimal string, log the error and use the incoming string as the outgoing string, marking the request as an error.
        outgoing_str = self.model.generate(incoming_str)
        try:
            # convert the outgoing string back to raw bytes to send it over the TCP connection. If conversion fails, log the error and use the incoming string as the outgoing string, marking the request as an error.
            outgoing_raw = bytes.fromhex(outgoing_str)
        except:
            # if the model fails to generate a valid hexadecimal string, log the error and use the incoming string as the outgoing string, marking the request as an error.
            logger.error(f"IP: {client_ip}:{client_port} - Outgoing Error Encoding: {outgoing_str}")
            outgoing_raw = bytes.fromhex(incoming_str)
            client_request.error = True

        # send the generated response back to the client over the TCP connection and log the outgoing response details, including the client IP, port, raw bytes, and the converted string.
        self.request.sendall(outgoing_raw)

        # log the outgoing response details, including the client IP, port, raw bytes, and the converted string.
        logger.info(f"IP: {client_ip}:{client_port} - Outgoing String: {outgoing_str}, Outgoing Raw: {outgoing_raw}")

        # update the client request details with the response time and response string.
        client_request.response_time = datetime.now()
        client_request.response = outgoing_str

        client.requests.append(client_request)

        # save the client and request details to the database, ensuring that the client entry is updated with the new request and response information.
        await client.save(link_rule=WriteRules.WRITE)
        client_request.client = client.id.__str__()
        await client_request.save()


# open port 5020 and waits indefinitly for incoming TCP connections, handling each connection using the ThreadedTCPRequestHandler to process requests concurrently.
async def async_server():
    server = ThreadedTCPServer(("0.0.0.0", 5020), ThreadedTCPRequestHandler)
    server.serve_forever()


# initialize the MongoDB client, set up the Beanie ODM with the defined document models, and start the asynchronous TCP server to handle incoming Modbus requests. This function serves as the main entry point for the Modbus application, ensuring that all necessary components are initialized before accepting connections.
async def modbus_app():
    client = AsyncIOMotorClient('mongo', 27017, username='root', password=os.environ['MONGO_PWD'], authSource='admin')
    await init_beanie(database=client.modbus, document_models=[Client, Request], multiprocessing_mode=True)

    await async_server()


def main():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(modbus_app())


if __name__ == '__main__':
    main()
