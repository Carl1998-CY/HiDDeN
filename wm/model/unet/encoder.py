# encoding: utf-8

"""
Adapted from https://github.com/junyanz/pytorch-CycleGAN-and-pix2pix/blob/master/models/networks.py

"""
import functools
import torch
import torch.nn as nn
from wm.util.common import expand_message


# Defines the Unet generator.
# |num_downs|: number of downsamplings in UNet. For example,
# if |num_downs| == 7, image of size 128x128 will become of size 1x1
# at the bottleneck

class UnetGenerator(nn.Module):

    _kwargs_defaults = {
        'unet_ngf': 64, 
        'unet_output_function': nn.Tanh,
        'unet_norm_layer': nn.BatchNorm2d,
        'unet_use_dropout': False,
        'unet_down_blocks': 7
    }

    def __init__(self, num_downs: int, message_length: int, **kwargs):
        super(UnetGenerator, self).__init__()
        ngf = kwargs.pop('unet_ngf', self._kwargs_defaults['unet_ngf'])
        output_function = kwargs.pop('unet_output_function', self._kwargs_defaults['unet_output_function'])
        norm_layer = kwargs.pop('unet_norm_layer', self._kwargs_defaults['unet_norm_layer'])
        use_dropout = kwargs.pop('unet_use_dropout', self._kwargs_defaults['unet_use_dropout'])
        num_downs = kwargs.pop('unet_down_blocks', self._kwargs_defaults['unet_down_blocks'])
        input_nc = message_length + 3
        output_nc = 3

        unet_block = UnetSkipConnectionBlock(outer_nc=ngf * 8, inner_nc=ngf * 8, input_nc=ngf * 8 + message_length,
                                             submodule=None,
                                             norm_layer=norm_layer,
                                             innermost=True, 
                                             module_name='innermost')
        for i in range(num_downs - 5):
            unet_block = UnetSkipConnectionBlock(outer_nc=ngf * 8, inner_nc=ngf * 8, input_nc=ngf * 8 + message_length,
                                                 submodule=unet_block,
                                                 norm_layer=norm_layer, use_dropout=use_dropout,
                                                 module_name=f'module-{i+1}')
        unet_block = UnetSkipConnectionBlock(outer_nc=ngf * 4, inner_nc=ngf * 8, input_nc=ngf * 4 + message_length,
                                             submodule=unet_block,
                                             norm_layer=norm_layer,
                                             module_name=f'module-{num_downs-3}')
        unet_block = UnetSkipConnectionBlock(outer_nc=ngf * 2, inner_nc=ngf * 4, input_nc=ngf * 2 + message_length,
                                             submodule=unet_block, norm_layer=norm_layer, module_name=f'module-{num_downs-2}')
        unet_block = UnetSkipConnectionBlock(outer_nc=ngf, inner_nc=ngf * 2, input_nc=ngf + message_length,
                                             submodule=unet_block, norm_layer=norm_layer, module_name=f'module-{num_downs-1}')
        unet_block = UnetSkipConnectionBlock(outer_nc=output_nc, inner_nc=ngf, input_nc=input_nc, submodule=unet_block,
                                             outermost=True, norm_layer=norm_layer, output_function=output_function, module_name=f'outermost')

        self.model = unet_block

    def forward(self, image, message):
        return self.model(image, message)


# Defines the submodule with skip connection.
# X -------------------identity---------------------- X
#   |-- downsampling -- |submodule| -- upsampling --|
class UnetSkipConnectionBlock(nn.Module):
    def __init__(self, outer_nc, inner_nc, module_name, input_nc=None, submodule=None, outermost=False, innermost=False,
                 norm_layer=nn.BatchNorm2d, use_dropout=False, output_function=nn.Sigmoid):

        super(UnetSkipConnectionBlock, self).__init__()
        self.outermost = outermost
        self.module_name = module_name
        if type(norm_layer) == functools.partial:
            use_bias = norm_layer.func == nn.InstanceNorm2d
        else:
            use_bias = norm_layer == nn.InstanceNorm2d
        if input_nc is None:
            input_nc = outer_nc
        downconv = nn.Conv2d(input_nc, inner_nc, kernel_size=4,
                             stride=2, padding=1, bias=use_bias)
        downrelu = nn.LeakyReLU(0.2, True)
        downnorm = norm_layer(inner_nc)
        uprelu = nn.ReLU(True)
        upnorm = norm_layer(outer_nc)

        if outermost:
            upconv = nn.ConvTranspose2d(inner_nc * 2, outer_nc,
                                        kernel_size=4, stride=2,
                                        padding=1)
            down = [downconv]
            if output_function == nn.Tanh:
                up = [uprelu, upconv, nn.Tanh()]
            else:
                up = [uprelu, upconv, nn.Sigmoid()]
            model = down + [submodule] + up
        elif innermost:
            upconv = nn.ConvTranspose2d(inner_nc, outer_nc,
                                        kernel_size=4, stride=2,
                                        padding=1, bias=use_bias)
            down = [downrelu, downconv]
            up = [uprelu, upconv, upnorm]
            model = down + up
        else:
            upconv = nn.ConvTranspose2d(inner_nc * 2, outer_nc,
                                        kernel_size=4, stride=2,
                                        padding=1, bias=use_bias)
            down = [downrelu, downconv, downnorm]
            up = [uprelu, upconv, upnorm]

            if use_dropout:
                up.append(nn.Dropout(0.5))

        self.down = nn.Sequential(*down)
        self.submodule = submodule
        self.up = nn.Sequential(*up)
        # self.model = nn.Sequential(*model)

    def forward(self, x, message):
        expanded_message = expand_message(message, x.shape[2], x.shape[3])
        x_cat = torch.cat((x, expanded_message), 1)
        image_down = self.down(x_cat)
        if self.submodule is not None: # means we are at the innermost module
            image_down = self.submodule(image_down, message)
        image_up = self.up(image_down)
        if not self.outermost:
            image_up = torch.cat([image_up, x], 1)
        return image_up