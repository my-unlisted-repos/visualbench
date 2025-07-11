import warnings
from collections.abc import Callable
from typing import Any, Literal

import torch
from torch import nn
import torch.nn.functional as F

from ...benchmark import Benchmark
from ...utils import algebras, format
from . import linalg_utils


class StochasticMatrixRecovery(Benchmark):
    """Matrix recovery from matrix vector products.

    Args:
        A (Any, optional): (m, n). Defaults to 512.
        B (Any, optional): (m, ) or (m, k). Defaults to 512.
        criterion (Callable, optional): loss. Defaults to F.mse_loss.
        l1 (float, optional): L1 penalty. Defaults to 0.
        l2 (float, optional): L2 penalty. Defaults to 0.
        linf (float, optional): Linf penalty (penalty for maximum value). Defaults to 0.
        algebra (Any, optional): custom algebra for matmul. Defaults to None.
        seed (int, optional): seed. Defaults to 0.
    """
    def __init__(self, A:Any=512, batch_size: int = 1, criterion = F.mse_loss, l1:float=0, l2:float=0, linf:float=0, vec=True, algebra=None, seed=0):
        super().__init__(seed=seed)
        generator = self.rng.torch()
        self._make_images = False # will be True if A or B are an image.

        if isinstance(A, int): A = torch.randn(A, A, generator=generator)
        elif isinstance(A, tuple) and len(A) == 2: A = torch.randn(A, generator=generator)
        else:
            self._make_images = True
            A = format.to_CHW(A)
        self.A = nn.Buffer(A)
        self.B = nn.Parameter(torch.randn_like(self.A))

        self.batch_size = batch_size
        self.vec = vec
        self.criterion = criterion
        self.l1 = l1
        self.l2 = l2
        self.linf = linf

        self.algebra = algebras.get_algebra(algebra)

        if self._make_images:
            self.add_reference_image('A', A, to_uint8=True)

    def pre_step(self):
        if self.vec:
            *b, n, m = self.A.shape
            self.X = torch.randn((self.batch_size, *b, m, 1), device=self.A.device, dtype=self.A.dtype, generator=self.rng.torch(self.A.device))

        else:
            self.X = torch.randn((self.batch_size, *self.A.shape), device=self.A.device, dtype=self.A.dtype, generator=self.rng.torch(self.A.device))

    def get_loss(self):
        X = self.X

        AX = algebras.matmul(self.A, X, self.algebra)
        BX = algebras.matmul(self.B, X, self.algebra)

        penalty = 0
        if self.l1 != 0: penalty = penalty + torch.linalg.vector_norm(self.B, ord=1) # pylint:disable=not-callable
        if self.l2 != 0: penalty = penalty + torch.linalg.vector_norm(self.B, ord=2) # pylint:disable=not-callable
        if self.linf != 0: penalty = penalty + torch.linalg.vector_norm(self.B, ord=float('inf')) # pylint:disable=not-callable

        if self._make_images:
            self.log_image("B", self.B, to_uint8=True, log_difference=True)

        return self.criterion(AX, BX) + penalty

