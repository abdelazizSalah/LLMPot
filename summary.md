Dear Professor,

I hope this email finds you well and that you are enjoying your vacation.

I  would like to provide you with a brief update on the current state of the project and summarize the work I have completed during the previous period.

I did the following:
1.  Contacted Marco to request access to public datasets. He informed me that the private datasets are available on the server; however, since Joachim was unavailable, I plan to contact him after the vacation to request access.

2.  Began working with the WDT Modbus dataset and carefully studied its corresponding paper to fully understand the dataset structure and characteristics.

3.  analyzed how LLMPot parses PCAP files and successfully adapted it to parse WDT PCAP files, generating training, validation, and testing datasets in the same manner described in LLMPot paper, both with and without context.

4.  developed a script to extract dataset configuration parameters directly from the PCAP files, such as packet length, minimum and maximum values, minimum and maximum addresses, and the number of used coils and registers.

5.  generated multiple sample sizes from the normal WDT traffic (1k, 10k, 100k, and 1,000k samples).

6.  prepared a detailed write-up describing how to train LLMPot on a custom dataset.

7.  initiated training on 10k samples on the haiti server; the process took approximately one day and 13 hours. When attempting to evaluate the trained model, I noticed that the inference class in the original repository is incomplete and contains messy structured code, making it difficult to understand how inference is performed. I plan to address this issue after returning from vacation.

8.  successfully deployed Honeyd on Ubuntu 22.04. Previously, it was only functional on Ubuntu 18.04. I deployed it using the configuration file provided by LLMPot and verified its correct operation by testing it from Kali Linux.

9.  also managed to run the provided Docker containers, including the MongoDB container for logging honeypot interactions and the container hosting the PLC website. While these containers run correctly on a local machine, I was unable to deploy them on the server due to the required elevated privileges. As a result, I deployed Honeyd and the containers on my local virtual machine instead.

10.  couldn't figure out how they deploy the LLM as a background service, because this is the only missing component, and it is the main one, but I will try it again to

11.  considered the process of building a honeypot configuration from collected logs and outlined a potential workflow:

    1. Collect the logs

    2. Extract unique IP addresses, ports, and MAC addresses

    3. Identify communication relationships between IP addresses and ports to infer the network topology

    4. Determine the types of devices involved (e.g., mapping specific IP addresses to PLCs or HMIs); at this stage, it is unclear how this information can be reliably inferred from logs alone

    5. Use the extracted information to generate the Honeyd configuration file

    6. Deploy and run the honeypot

12.  looked for the other project idea rather than the build honeypot from logs, but I did not find it.

Unfortunately, I was unable to borrow the PLC from Margo for testing purposes, as we did not meet after the vacation began.

Regarding log analysis, I believe that the dashboard provided by ICSPot could be leveraged for this purpose.


Kind regards,
Abdelaziz Neamatallah