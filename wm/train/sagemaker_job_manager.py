import sys
import os
import logging
import json
from pathlib import Path
from pprint import pformat
import torch
import shutil

import util.common as common
from noise.noiser import Noiser
# from train.tensorboard_logger import TensorBoardLogger
from torch.utils.tensorboard import SummaryWriter
from train.train_model import train
from model.hidden.hidden_model import Hidden
from model.unet.unet_model import UnetModel


class SagemakerJobManager:
    def __init__(self, args):
        
        self.resume_mode = args.main_command == 'resume'
        # if self.resume_mode:
        #     self.config = json.load(open(os.path.join(args.folder, 'config.json')))
        # else:
        self.config = args.__dict__.copy()
        self.config['timestamp'] = common.get_timestamp()
        self.config['noise'] = '+'.join(sorted(self.config['noise'].split('+')))
        self.config['job_name'] = self._job_name()
        # self.config['job_folder'] = os.path.join(self.config['jobs_folder'], self.config['job_name'])
        # self.config['job_folder'] = 
        # if self.config['tensorboard']:
        #     noise_folder = self.config['noise'] if self.config['noise'] else 'no-noise'
        #     self.config['tensorboard_folder'] = os.path.join(self.config['tb_folder'], noise_folder, 
        #         f'{self.config["timestamp"]}--{self.config["main_command"].lower()}')
        if 'data' in self.config:
            self.config['train_folder'] = os.path.join(self.config['data'], 'train')
            self.config['val_folder'] = os.path.join(self.config['data'], 'val')
                    
        self.tb_writer = None
        

    def start_or_resume(self):
        print(f'Before create model')
        self.model = self._create_model()        
        if not self.resume_mode:
            self._create_job_folders()
            self._save_config()

        if self.config['tensorboard']:
            print(f'Create tensorboard')
            print(f'log dir: {self.config["tensorboard_folder"]}')
            self.tb_writer = SummaryWriter(log_dir=self.config['tensorboard_folder'])
        
        print('Tensorboard created')
        print('Create loggers')
        logging.basicConfig(level=logging.INFO,
        format='%(message)s',
        handlers=[
            logging.FileHandler(os.path.join(self.config['job_folder'], f'{self.config["job_name"]}.log')),
            logging.StreamHandler(sys.stdout)
        ])
        logging.info(self.model)
        print('Done.')
        if self.resume_mode:
            checkpoint, checkpoint_file = common.load_last_checkpoint(os.path.join(self.config['job_folder'], 'checkpoints'))
            start_epoch = checkpoint['epoch'] + 1
            logging.info(f'Loaded checkpoint job checkpoint from file: {checkpoint_file}')
            common.model_from_checkpoint(self.model, checkpoint)
            logging.info(f'Training will resume from epoch={start_epoch}')
        else:
            start_epoch = 1
            logging.info(f'Model:\n{str(self.model)}')
            logging.info(f'Configuration: {pformat(self.config, indent=4)}')
            
        print(f'Before train command')
        train(model=self.model, job_name=self.config['job_name'], job_folder=self.config['job_folder'], 
            image_size=self.config['size'], train_folder=self.config['train_folder'],
            validation_folder=self.config['val_folder'], 
            batch_size=self.config['batch_size'], 
            message_length=self.config['message'],
            number_of_epochs=self.config['epochs'], 
            start_epoch=start_epoch, 
            tb_writer=self.tb_writer, 
            checkpoint_folder=self.config['checkpoint_folder'])
        
        logging.info(f'Copy the last checkpoint file into {self.config["model_folder"]}')
        checkpoint_filename = f'{self.config["job_name"]}--last.pyt'
        print('before trying to copy checkpoint')
        print(f'checkpoint_filename: {checkpoint_filename}')
        src = os.path.join(self.config['checkpoint_folder'], checkpoint_filename)
        dst = os.path.join(self.config['model_folder'], checkpoint_filename)
        print(f'Attempting to copy source file from {src} to {dst}')
        # checkpoint_filename = os.path.join(self.config["checkpoint_folder"], checkpoint_filename)
        shutil.copyfile(src=src, dst=dst)
        print(f'copy successful')
        
    def _create_job_folders(self):
        job_folder = self.config['job_folder']
        Path(job_folder).mkdir(parents=True, exist_ok=True)
        os.makedirs(os.path.join(job_folder, 'checkpoints'))
        os.makedirs(os.path.join(job_folder, 'images'))
        Path(self.config['checkpoint_folder']).mkdir(parents=True, exist_ok=True)
        if self.config['tensorboard']:
            print(f'Creating tensorboard folder')
            print(f'Tensorboard folder is: {self.config["tensorboard_folder"]}')
            Path(self.config['tensorboard_folder']).mkdir(parents=True, exist_ok=True)
            print(f'Done')
            print(f'Check if path exists...')
            print(f'Path.exists: {Path(self.config["tensorboard_folder"]).exists()}')

    def _job_name(self):
        job_name = f'$$timestamp--$$main-command--$$noise'
        if self.config['jobname_suffix']:
            job_name = job_name + '--' + self.config['jobname_suffix']
        job_name = job_name.replace('$$timestamp', self.config['timestamp'])
        job_name = job_name.replace('$$main-command', self.config['main_command'].lower())
        if self.config['noise']:
            job_name = job_name.replace('$$noise', self.config['noise'])
        else:
            job_name = job_name.replace('--$$noise', '')
        return job_name


    def _save_config(self):
        with open(os.path.join(self.config['job_folder'], 'config.json'), 'w') as f:
            json.dump(self.config, f)


    def _create_model(self):
        if self.config['main_command'].lower() == 'hidden':
            model = Hidden(**self.config)
        elif self.config['main_command'].lower() in ['unet-conv', 'unet-attn', 'unet-down']:
            model = UnetModel(**self.config)
        return model
        