- To run any script in this folder, we must run it as follows:
  - > python -m (folder_name.sub_folder_name.script_name.py)

- running command:
python -m src.finetune.multi_trainer -p 200:1,400:1,800:1,1600:1,3200:1,6400:1 -model byt5-small -cfg s7comm-protocol-emulation.json