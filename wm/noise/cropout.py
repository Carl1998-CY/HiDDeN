import torch
import torch.nn as nn
from wm.noise.func import get_random_rectangle_inside


class Cropout(nn.Module):
    """
    Combines the noised and cover images into a single image, as follows: Takes a crop of the noised image, and takes the rest from
    the cover image. The resulting image has the same size as the original and the noised images.
    """
    def __init__(self, cropout_min: float, cropout_max: float):
        super(Cropout, self).__init__()
        self.cropout_min = cropout_min
        self.cropout_max = cropout_max

    def forward(self, noised_and_cover):
        noised_image = noised_and_cover[0]
        cover_image = noised_and_cover[1]
        assert noised_image.shape == cover_image.shape

        cropout_mask = torch.zeros_like(noised_image)
        h_start, h_end, w_start, w_end = get_random_rectangle_inside(image=noised_image,
                                                                     height_ratio_range=(self.cropout_min, self.cropout_max),
                                                                     width_ratio_range=(self.cropout_min, self.cropout_max))
        cropout_mask[:, :, h_start:h_end, w_start:w_end] = 1
        return noised_image * cropout_mask + cover_image * (1-cropout_mask)

    def __repr__(self):
        return f'cropout({self.cropout_min},{self.cropout_max})'