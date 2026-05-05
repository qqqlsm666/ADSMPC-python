"""
.. note::
    * csprng only support the Python3.8.0
    * AES requires two int64 (128bit) per seed
"""
#  This file is part of the NssMPClib project.
#  Copyright (c) 2024 XDU NSS lab,
#  Licensed under the MIT license. See LICENSE in the project root for license information.

import torch

try:
    import torchcsprng as csprng
except ImportError:
    csprng = None


class AES:
    def __init__(self, seeds):
        """
        Using AES algorithm to generate random numbers.

        :param seeds: seeds generated from pseudo-random numbers
        :type seeds: int
        """
        self.s = seeds

    def bit_random(self, bits):
        """
        Cryptographically Secure Pseudo-Random Number Generator for PyTorch

        Each seed generates 'bits' bits of pseudo-random numbers, carried in int64, independent of *BIT_LEN*

        :param bits: The bit width of the random number is required
        :type bits: int
        :return: The first dimension is the number of parallelizations (seeds), and the second dimension is the int64 required to carry bits of random numbers
        :rtype: torch.Tensor
        """
        if csprng is not None:
            return csprng.random_repeat(self.s, bits)

        # Fallback for demo environments without the torchcsprng C++ extension.
        # This is not cryptographically secure.
        seeds = self.s.detach().cpu().to(torch.int64)
        if seeds.dim() == 0:
            seeds = seeds.view(1, 1)
        elif seeds.dim() == 1:
            seeds = seeds.view(-1, 1)
        else:
            seeds = seeds.reshape(seeds.shape[0], -1)
        cols = max(1, (bits + 63) // 64)
        rows = []
        for seed_row in seeds:
            seed = int(seed_row[0].item())
            for item in seed_row[1:]:
                seed ^= int(item.item())
            generator = torch.Generator(device='cpu')
            generator.manual_seed(seed & 0xFFFFFFFFFFFFFFFF)
            rows.append(torch.randint(
                torch.iinfo(torch.int64).min,
                torch.iinfo(torch.int64).max,
                (cols,),
                generator=generator,
                dtype=torch.int64,
            ))
        return torch.stack(rows, dim=0)
