import argparse
from argparse import ArgumentParser
import os

import pickle
import json
import logging
import sys

import torch
from pprint import pprint, pformat
import wm.util.configuration as cfg
import wm.train.job_manager as jobman 


def create_new_run_subparser(newrun_parser: ArgumentParser, network_type: str):
    recognized_networks = ['hidden', 'unet-conv', 'unet-attn']
    if network_type not in recognized_networks:
        raise ValueError(f'network type must be one of {recognized_networks}, instead it is "{network_type}".') 
    
    if network_type == 'hidden':
        defaults = cfg.hidden_defaults
    elif network_type == 'unet-conv':
        defaults = cfg.unet_conv_defaults
    elif network_type == 'unet-down':
        defaults = cfg.unet_down_defaults
    elif network_type == 'unet-attn':
        defaults = cfg.unet_attn_defaults

    newrun_parser.add_argument('--data-dir', '-d', default='./data/medium', type=str, help='The input data directory')
    newrun_parser.add_argument('--batch-size', '-b', default=32, type=int, help='The batch size.')
    newrun_parser.add_argument('--epochs', '-e', default=300, type=int, help='Number of epochs to run the simulation.')
    newrun_parser.add_argument('--name', default='', type=str, help='The name of the experiment.')
    newrun_parser.add_argument('--job-name', default='$$timestamp--$$main-command--$$noise', type=str, help='String representation for the experiment name')
    newrun_parser.add_argument('--jobs-folder', default='./jobs', type=str, help='The root folder of experiments')
    newrun_parser.add_argument('--tb-folder', default='./tb-logs', type=str, help='The root tensorboard folder')

    newrun_parser.add_argument('--size', '-s', default=128, type=int,
                                help='The size of the images (images are square so this is height and width).')
    newrun_parser.add_argument('--message', '-m', default=30, type=int, help='The length in bits of the watermark.')
    newrun_parser.add_argument('--no-tensorboard', action='store_false', dest='tensorboard',
                                help='Turn off TensorBoard logging.')
    newrun_parser.add_argument('--enable-fp16', dest='enable_fp16', action='store_true',
                                help='Enable mixed-precision training.')
    newrun_parser.add_argument('--device', default='cuda', type=str, choices=['cuda', 'cpu'], help='The device, cuda|cpu.')

    newrun_parser.add_argument('--enc-loss-weight', default=defaults['enc-loss-weight'],  type=float,
                                help='The weight of encoder loss in the overall loss function')
    newrun_parser.add_argument('--adv-loss-weight', default=defaults['adv-loss-weight'],  type=float,
                                help='The weight of the adversarial loss in the overall loss function')

    newrun_parser.add_argument('--encoder-blocks', default=defaults['encoder-blocks'],  type=str, help='Number of blocks in the encoder.')
    newrun_parser.add_argument('--encoder-channels', default=defaults['channels'],  type=int, help='Number of inner channels in encoder blocks.')
    newrun_parser.add_argument('--encoder-block-type', default=defaults['encoder-block-type'], 
                                choices=['Conv', 'Unet'], type=str, help='Encoder block type.')

    newrun_parser.add_argument('--decoder-blocks', default=defaults['decoder-blocks'], type=int, help='Number of blocks in the decoder')
    newrun_parser.add_argument('--decoder-channels', default=defaults['channels'], type=int, help='Number of channels in decoder blocks.')
    newrun_parser.add_argument('--decoder-block-type', default=defaults['decoder-block-type'], choices=['Conv', 'Unet'], 
                                type=str, help='Decoder block type.')

    newrun_parser.add_argument('--discriminator-blocks', default=defaults['discriminator-blocks'], type=str, help='Number of blocks in the discriminator.')
    newrun_parser.add_argument('--discriminator-channels', default=defaults['channels'], type=str, help='Number of channels in discriminator blocks.')
    newrun_parser.add_argument('--discriminator-block-type', default=defaults['discriminator-block-type'], 
                                choices=['Conv', 'Unet'], type=str, help='discriminator block type')

    newrun_parser.add_argument('--adam-lr', default=defaults['adam-lr'], type=float, help='Learning rate of Adam')

    newrun_parser.add_argument('--noise', type=str, default='',
                                help="Noise layers configuration. Use quotes when specifying configuration, e.g. 'cropout((0.55, 0.6), (0.55, 0.6))'")

    newrun_parser.set_defaults(tensorboard=True, enable_fp16=False)
    

def main():
    
    parent_parser = argparse.ArgumentParser(usage='hidden|unet-conv|unet-down|resume')

    subparsers = parent_parser.add_subparsers(dest='main_command', required=True)
    hidden_parser = subparsers.add_parser('hidden', help='HiDDeN architecture')
    create_new_run_subparser(hidden_parser, 'hidden')

    unet_conv_parser = subparsers.add_parser('unet-conv', help='Unet encoder with HiDDeN decoder')
    create_new_run_subparser(unet_conv_parser, 'unet-conv')

    # unet_down_parser = subparsers.add_parser('unet-down', help='Unet encoder with downsampling decoder')
    # create_new_run_subparser(unet_down_parser, 'unet-down')
    unet_attn_parser = subparsers.add_parser('unet-attn', help='Unet attention encoder with decoder')
    create_new_run_subparser(unet_attn_parser, 'unet-attn')

    resume_parser = subparsers.add_parser('resume', help='Resume a previous run')
    resume_parser.add_argument("folder", type=str,
                                help='Continue from the last checkpoint in this folder.')

    resume_parser.add_argument('--no-tensorboard', action='store_false', dest='tensorboard',
                                help='Turn off TensorBoard logging.')
    resume_parser.set_defaults(tensorboard=True)

    args = parent_parser.parse_args()

    job = jobman.JobManager(args)
    print('-'*80)
    pprint(job.config)
    job.start_or_resume()

    
if __name__ == "__main__":
    main()