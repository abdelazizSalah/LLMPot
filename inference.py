# Import three HuggingFace components
'''
AutoTokenizer: Responsible for converting raw input text to the model's token IDs
                LLMpot model uses byte-level tokenizer, matching ByT5's architecture

AutoModelForSeq2SeqLM: Loads a sequence-to-sequence model (ByT5-small)
                     LLMPot works as machine translation:
                        Input: Modbus request in hex string format
                        Output: Corresponding Modbus response in hex string format
Pipeline: A huggingFace helper that simplifies inference
Handles tokenization, model forwarding, and decoding.



'''


from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline

# load the tokenizer stored inside LLMPot model repository
# the tokenizer is byte-level, meaning it understands raw bytes as input including 00 up to FF
# This is valid for protocols.
tokenizer = AutoTokenizer.from_pretrained("cv43/llmpot")

# This loads the fine-tuned LLMPot modbus emulator model.
# Inside the huggingFace repo, it should find:
    # model.safetensors: 1.2 GB weights file
    # config.json: model architecture config
    # generation_config.json: decoding settings
# So the model has already been fine-tuned on modbus request-response pairs.
model = AutoModelForSeq2SeqLM.from_pretrained("cv43/llmpot")

# Create high-level inference engine
# The pipeline automatically:
#   1. Tokenizes the input Modbus request.
#   2. Runs it through the LLMPot model.
#   3. Decodes the output tokens into a modbus response hex string.
pipe = pipeline("text2text-generation", model=model, tokenizer=tokenizer)


'''
Example Modbus request:
    - [1,2] two bytes: transaction ID (02 1b)
    - [3,4] two bytes: protocol ID (00 00)
    - [5,6] two bytes: length (00 08)
    - [7] byte: unit ID (00)
    - [8] byte: function code (06 = write single register)
    = 0002000200ffffff ??
    = target register address: 0002
    = value to write: 0002
    =

    https://www.fernhillsoftware.com/help/drivers/modbus/modbus-protocol.html
    I got many examples from here, and the results from LLMPot never correct.
'''
request = "021b00000008000600020002"
# request = "00 0A 00 00 00 06 01 02 01 F4 00 20".replace(" ", "")
response = pipe(request)

print(response)
print("Response:", response[0]["generated_text"])
