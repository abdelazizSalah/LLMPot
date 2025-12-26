'''
@Reviewer: Abdelaziz Neamatallah
@Date: 10.12.25
@Description: Trying to understand how this works, and train the model on my dataset not on the default one.
'''


# for timestamps
import datetime
import os
import time

# For datatypes
from typing import List, Optional

# valid percision formats for lighting
from lightning.fabric.plugins.precision.precision import _PRECISION_INPUT


# authors modules for checkpoints and logging.
from src.cfg import CHECKPOINTS, LOGS
from src.finetune.model.database_model import DatasetModel
from src.finetune.model.lora import Lora


# This class is a container for inference-only experiments, used for evaluating the model.
class TestExperiment:
    experiment: str
    dataset: str

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


# This class is central configuration object for everything related to training
#? usage for my case: python ./src/finetune/multi-trainer.py -p 200:1,400:1,800:1,1600:1,3200:1,6400:1 -model byt5-small -cfg s7comm-protocol-emulation.json
class FinetunerModel:

    model_type: str # for example google module
    model_name: str # its main name, like byt5-small

    # The name of the experiment, usually a timestamp
    experiment: str

    # All dataset objects
    current_dataset: DatasetModel # => this is where I can modify the dataset used for training

    # This is read from JSON file exist in experiments folder, which similar to the configuration file shown in the paper.
    datasets: List[DatasetModel] # => all dataset objects -> train, val, and test.
    experiment_filename: str = "" # input json filename for the experiment configuration
    test_experiment: Optional[TestExperiment] = None

    # LLMPot hyperparameters
    max_epochs: int = 30
    patience: int = 10
    batch_size: int = 8
    target_max_token_len = 512
    source_max_token_len = 512
    precision: _PRECISION_INPUT = "32"
    workers: int = 2 # I think this should increase to speed up data loading

    start_time: float
    start_datetime: str

    checkpoints_dir: str
    log_output_dir: str

    # Low-rank adaptation of LLM
    '''
    LORA video explaination: https://www.youtube.com/watch?v=DhRoTONcyZE&t=34s
        It is a lightweight method to fine-tune huge neural networks without updating all the parameters.
        Instead of training the full model (millions or billions of weights)
        LoRA inserts tiny trainable matrices inside the model and freezes the rest.

        So, Lora says:
            - Do not update the original weights, Add a small low-rank matrix A.B that learns the adaptation.

        Benfits of LoRA:
            - Normal fine-tuning of LLMs is expensive because
                - We must update hundreds of millions of weights.
                - Requires huge GPU memory.
                - Slow training and high energy.
            - Lora:
                - Freeze all original model weights.
                - insert small adapter
                - Only train the adapter weights.
                - Combine them with the frozen model at inference time.
            - So instead of traininal all model weights, they only train small portion of them.
        - So they used it to reduce the training time by training 40 million parameters instead of 300 millions, but they mentioned in the paper that this lead
        to poor results.
         .Finally,weuseLoRA[27]tominimizetraining
            time on the byt5-small model by training 40million
            instead of 300million parameters, but this also yields
            poorresultswhichcanbeattributedtothefact thatwere         => from the paper.
            purpose themodel’sobjective ingeneratinghexadecimal
            responses insteadofdoinglanguagetranslation.
    '''
    lora: Lora


    '''
        - It tells the library which hardware to use for training.
        - "cuda" means using NVIDIA GPUs.
        - so it runs the training on GPU instead of CPU.
        - when strategy is "ddp", it means Distributed Data Parallel.
        - which means distribute the model accross multiple GPUs for faster training.

    '''
    accelerator: str = "cuda" # This is PyTorch lightning accelerator
    # devices = len(str(os.getenv('CUDA_VISIBLE_DEVICES')).split(",")) if os.getenv('CUDA_VISIBLE_DEVICES') else 1
    devices = [1]  # use single GPU
    # strategy: str = "ddp" #"deepspeed_stage_2_offload"
    strategy: str = "auto" # use single GPU instead of multiple

    validation = ["exact", "validator"] # exact -> BCA, validator -> RVA

    # standard metric names for logging.
    val_loss_const: str = "val_loss"
    train_loss_const: str = "train_loss"

    def __init__(self, experiment: str, **kwargs):
        '''
            Constructor takes the experiment name, and other keyword arugments populated from JSON configuration file.
            - then it handles special cases:
                - if key is "lora", it creates Lora object.
                - if key is "datasets", it creates list of DatasetModel objects.
                - if key is "test_experiment", it creates TestExperiment object.

        '''
        for key, value in kwargs.items():
            if key == "lora":
                self.lora = Lora(**value)
            elif key == "datasets":
                self.datasets = [DatasetModel(**x) for x in value]
            elif key == "test_experiment":
                self.test_experiment = TestExperiment(**value)
            else:
                setattr(self, key, value)
        # define logging and checkpoint directories
        self.checkpoints_dir = CHECKPOINTS
        self.log_output_dir = LOGS

        # set start time and datetime for experiment instance
        self.start_time = time.time()
        self.start_datetime = datetime.datetime.fromtimestamp(self.start_time).strftime('%Y%m%dT%H%M')

        # assign experiment name
        self.experiment = experiment

        # assign the current dataset to the first dataset in the list
        self.current_dataset = self.datasets[0]

    def __str__(self):
        '''
            String representation of the experiment instance.
            - combines the dataset name and start datetime.
        '''
        return f"{self.the_name}_{self.start_datetime}"

    def base_model_id(self):
        '''
            Returns the base model identifier in the format "model_type/model_name".
        '''
        return f"{self.model_type}/{self.model_name}"

    @property
    def the_name(self):
        '''
            Returns the name of the current dataset as string.
        '''
        return str(self.current_dataset)

    def get_validation_filename(self, epoch: int, validation_type: str):
        '''
            Creates a folder for the experiment results
            - if it was test experiment, it uses experiment_dataset_result_path along with validation type and current dataset.
            - else it uses experiment_instance_result_path along with epoch number and validation type.

        '''
        if self.test_experiment:
            path = f"{self.experiment_dataset_result_path}/val_type_{validation_type}-model_{self.current_dataset}.jsonl"
        else:
            path = f"{self.experiment_instance_result_path}/epoch-{epoch}_val_type-{validation_type}.jsonl"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    @property
    def experiment_model_result_path(self):
        return f"{CHECKPOINTS}/{self.model_name}"

    @property
    def experiment_result_path(self):
        return f"{self.experiment_model_result_path}/{self.experiment}"

    @property
    def experiment_dataset_result_path(self):
        return f"{self.experiment_result_path}/{self.current_dataset}"

    @property
    def experiment_instance_result_path(self):
        return f"{self.experiment_dataset_result_path}/{self.start_datetime}"

    @property
    def experiment_instance_last_result_path(self):
        return f"{self.experiment_instance_result_path}/checkpoints/last.ckpt"

    @property
    def experiment_csv_metrics_path(self):
        return f"{self.experiment_dataset_result_path}/csv/{self.start_datetime}/metrics.csv"
