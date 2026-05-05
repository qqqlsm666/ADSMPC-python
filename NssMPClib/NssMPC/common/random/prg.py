#  This file is part of the NssMPClib project.
#  Copyright (c) 2024 XDU NSS lab,
#  Licensed under the MIT license. See LICENSE in the project root for license information.

import torch

try:
    # Windows: torchcsprng 编译版的 _C.pyd 依赖 torch 的 DLL（c10/torch_cpu/torch_python），
    # 但 Python 的 DLL 搜索路径不会自动包含 torch/lib，所以先把它加进去再 import。
    import os as _os
    _torch_lib_dir = _os.path.join(_os.path.dirname(torch.__file__), 'lib')
    if hasattr(_os, 'add_dll_directory') and _os.path.isdir(_torch_lib_dir):
        try:
            _os.add_dll_directory(_torch_lib_dir)
        except (FileNotFoundError, OSError):
            pass
    import torchcsprng
    from torchcsprng import PRG as AES_PRG
    HAS_TORCHCSPRNG = True
except ImportError:
    torchcsprng = None
    HAS_TORCHCSPRNG = False

    class AES_PRG:
        """
        Compatibility fallback used when torchcsprng cannot be built locally.

        This uses torch.Generator and is not a cryptographically secure PRG.
        It exists so demos and tests can run on Windows environments where the
        old torchcsprng extension is incompatible with the installed PyTorch.
        """

        def __init__(self):
            self.device = DEVICE
            self.parallel_num = 0
            self.generators = []

        def set_seeds(self, seeds):
            seeds = seeds.detach().cpu().to(torch.int64)
            if seeds.dim() == 0:
                seeds = seeds.view(1, 1)
            elif seeds.dim() == 1:
                seeds = seeds.view(-1, 1)
            else:
                seeds = seeds.reshape(seeds.shape[0], -1)
            self.parallel_num = seeds.shape[0]
            self.generators = []
            for seed_row in seeds:
                seed = int(seed_row[0].item())
                for item in seed_row[1:]:
                    seed ^= int(item.item())
                generator = torch.Generator(device='cpu')
                generator.manual_seed(seed & 0xFFFFFFFFFFFFFFFF)
                self.generators.append(generator)

        def bit_random(self, bits):
            if self.parallel_num == 0:
                return torch.empty(0, dtype=torch.int64, device=self.device)
            cols = max(1, (bits + 63) // 64)
            rows = [
                torch.randint(
                    torch.iinfo(torch.int64).min,
                    torch.iinfo(torch.int64).max,
                    (cols,),
                    generator=generator,
                    dtype=torch.int64,
                )
                for generator in self.generators
            ]
            out = torch.stack(rows, dim=0)
            # Generators 只能在 cpu 上工作；如果调用方期望 DEVICE 上的 tensor 就要拷过去
            if self.device != 'cpu':
                out = out.to(self.device)
            return out

        def random(self, length):
            if self.parallel_num == 0:
                return torch.empty(0, dtype=torch.int64, device=self.device)
            rows = [
                torch.randint(
                    torch.iinfo(torch.int64).min,
                    torch.iinfo(torch.int64).max,
                    (length,),
                    generator=generator,
                    dtype=torch.int64,
                )
                for generator in self.generators
            ]
            out = torch.stack(rows, dim=0)
            if self.device != 'cpu':
                out = out.to(self.device)
            return out

from NssMPC.common.ring.ring_tensor import RingTensor
from NssMPC.config import DEVICE, data_type, DTYPE


class PRG(object):
    """
    Seed parallel pseudo-random number generators used to generate pseudo-random numbers,
    which can be implemented using libraries such as random, PyTorch, MT, TMT, etc.
    """

    def __init__(self, kernel='AES', device=None):
        """
        Initializes a pseudo-random number generator(The default is AES).

        Create an **AES_PRG** instance for the actual random number generation

        ATTRIBUTES:
            * **kernel** (*str*): Specifies the random number generation algorithm to use(AES)
            * **device** (*str*): parameter of apparatus(CPU or GPU)
            * **_prg** (*PRG*): AES_PRG instance
            * **dtype** (*Type*): The data type of the seed
        """
        self.kernel = kernel
        self._prg = AES_PRG()
        self.dtype = None

    @property
    def device(self):
        """
        Get device type.

        :return: the device of the current PRG
        :rtype: str
        """
        return self._prg.device

    @property
    def parallel_num(self):
        """
        The number of seeds that can generate random numbers simultaneously.

        :return: The number of concurrent PRGS currently.
        :rtype: int
        """
        return self._prg.parallel_num

    def set_seeds(self, seeds):
        """
        Set the seed for PRG.

        The seed of this PRG is parallelized, which can simultaneously generate multiple pseudo-random numbers
        corresponding to multiple seeds.

        .. note::
            Here, 'seeds' is a tensor, where each element inside the tensor represents a seed.

        :param seeds: each element inside the tensor represents a seed.
        :type seeds: RingTensor or torch.Tensor
        """
        if isinstance(seeds, RingTensor):
            self.dtype = seeds.dtype
            self._prg.set_seeds(seeds.tensor.contiguous())
        elif isinstance(seeds, torch.Tensor):
            self._prg.set_seeds(seeds.contiguous())

    def bit_random_tensor(self, bits, device=None):
        """
        Generate a tensor containing n-bit random numbers that can be generated in parallel,
        with the number of parallel operations matching the number of seed values.

        :param bits: the bit number of random numbers.
        :type bits: int
        :param device: parameter of apparatus(CPU or GPU)
        :type device: str
        :returns: A tensor containing n-bit random numbers.
        :rtype: tensor
        """
        if self.parallel_num == 0:
            raise ValueError("seeds is None, please set seeds first!")
        gen = self._prg.bit_random(bits)
        if device is not None and device != self.device:
            gen = gen.to(device)
        return gen

    def random_tensor(self, length, device=None):
        """
        Generate a tensor containing n-bit random numbers that can be generated in parallel,
        with the number of parallel operations matching the number of seed values.

        :param length: the length of random numbers.
        :type length: int
        :param device: parameter of apparatus(CPU or GPU)
        :type device: str

        :returns: A tensor containing n-bit random numbers.
        :rtype: tensor

        .. note::
            Similar to :py:meth:`bit_random_tensor`, but the length of the generated random number is specified by the length parameter.
        """
        if self.parallel_num == 0:
            raise ValueError("seeds is None, please set seeds first!")
        gen = self._prg.random(length)
        if device is not None and device != self.device:
            gen = gen.to(device)
        return gen

    def bit_random(self, bits, dtype=None, device=None):
        """
        Create a RingTensor containing n-bit random numbers that can be generated in parallel,
        with the number of parallel operations matching the number of seed values.

        :param bits: The bit number of random numbers
        :type bits: int
        :param dtype: The data type of the seed
        :type dtype: Type
        :param device: Parameter of apparatus (CPU or GPU)
        :type device: str

        :returns: A RingTensor, which is a random number with n bits
        :rtype: RingTensor

        .. note::
            The difference between bit_random and bit_random_tensor is that the random number result generated by bit_random_tensor is of type tensor, while the result generated by bit_random is of type RingTensor.

        """
        if dtype is None:
            dtype = self.dtype
        if device is None:
            device = self.device
        gen = self.bit_random_tensor(bits)
        return RingTensor(gen, dtype, device)

    def random(self, length, dtype=None, device=None):
        """
        Create a RingTensor containing random numbers that can be generated in parallel,
        The length is determined by the *length* parameter.

        :param length: The length of the random numbers
        :type length: int
        :param dtype: The data type of the seed
        :type dtype: Type
        :param device: Parameter of apparatus (CPU or GPU)
        :type device: str
        :returns: A RingTensor, which is a random number with the specified shape
        :rtype: RingTensor
        """
        if dtype is None:
            dtype = self.dtype
        if device is None:
            device = self.device
        gen = self.random_tensor(length)
        return RingTensor(gen, dtype, device)


class MT19937_PRG():
    """
    The Mersenne Twister algorithm is used to generate pseudo-random numbers.
    """

    def __init__(self, dtype=data_type, device=DEVICE):
        """
        * **device** (*str*): Parameter of apparatus (CPU or GPU)
        * **dtype** (*Type*): The data type of the seed
        """
        self.dtype = dtype
        self.device = device
        self.generator = None

    def set_seeds(self, seed):
        """
        Create a Mersenne Twister random number generator.

        :param seed: A seed used to initialize a random number generator
        :type seed: int
        """
        if HAS_TORCHCSPRNG:
            self.generator = torchcsprng.create_mt19937_generator(seed)
        else:
            self.generator = torch.Generator(device='cpu')
            self.generator.manual_seed(int(seed) & 0xFFFFFFFFFFFFFFFF)

    def random(self, length, dtype=DTYPE):
        """
        Create a RingTensor containing random numbers. The length is determined by the *length* parameter.

        First, create an empty tensor of the specified length, then use *self.generator* to generate random numbers.

        :param length: Specifies the length of the generated random number
        :type length: int
        :param dtype: Specifies the type of data to return
        :type dtype: str
        :return: A RingTensor, which is a random number with the specified shape
        :rtype: RingTensor
        """
        return RingTensor(
            torch.empty(length, dtype=self.dtype, device=self.generator.device).random_(torch.iinfo(self.dtype).min,
                                                                                        to=None,
                                                                                        generator=self.generator),
            dtype)
