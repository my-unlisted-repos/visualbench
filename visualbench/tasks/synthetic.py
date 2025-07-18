"""synthetic funcs"""
import math
from collections.abc import Callable
from typing import Any, Literal, cast

import torch
from torch import nn
from torch.nn import functional as F

from ..benchmark import Benchmark
from ..utils import algebras, to_CHW, to_square, totensor


class Sphere(Benchmark):
    """Sphere benchmark (or other function depending on criterion).

    Directly minimizes `criterion` between `target` and `init`.

    Args:
        target (Any): if int, used as number of dims, otherwise is the target itself.
        init (Any, optional): initial values same shape as target, if None initializes to zeros. Defaults to None.
        criterion (Callable, optional): loss function. Defaults to torch.nn.functional.mse_loss.
    """
    def __init__(self, target: Any, init=None, criterion = torch.nn.functional.mse_loss,):
        super().__init__()

        # target tensor
        if isinstance(target, int): target = torch.randn(target, dtype=torch.float32, generator=self.rng.torch())
        self.target = torch.nn.Buffer(totensor(target).float())

        # preds tensor
        if init is None: init = torch.zeros_like(self.target)
        self.x = torch.nn.Parameter(totensor(init).float().contiguous())
        self.criterion = criterion

        # reference image for plotting
        if self.target.squeeze().ndim in (2, 3):
            self.add_reference_image('target', self.target.squeeze(), to_uint8=True)
            # enable showing best solution so far

    def get_loss(self):
        # log current recreated image if target is an image
        if self._make_images and len(self._reference_images) != 0:
            self.log_image('preds', self.x, to_uint8=True, log_difference=True)

        # return loss
        return self.criterion(self.x, self.target)


class Quadratic(Benchmark):
    """Basic convex quadratic objective with linear term.

    Args:
        dim (int, optional): number of dimensions. Defaults to 512.
        eps (int, optional): to make sure matrix is positive definite. Defaults to 1e-8.
        shift (bool | None, optional): shifts loss so that minimal loss is close to 0 (not exactly due to imprecision)
        seed (int, optional): rng seed. Defaults to 0.
    """
    def __init__(self, dim=512, eps=1e-4, algebra=None, shift=None, seed=0):
        super().__init__(seed=seed)
        generator = self.rng.torch()
        self.dim = dim

        H = torch.randn(dim, dim, generator=generator)
        self.H = torch.nn.Buffer((H @ H.mT) + torch.eye(dim)*eps) # positive definite matrix
        self.b = torch.nn.Buffer(torch.randn(dim, generator=generator))
        self.target = torch.nn.Buffer(torch.randn(dim, generator=generator))

        self.x = torch.nn.Parameter(torch.randn(dim, generator=generator))
        self.algebra = algebras.get_algebra(algebra)

        self.min_value = None
        if shift is None: shift = (algebra is None) and (dim <= 10_000)
        if shift:
            # shift so that minimal value is 0
            try:
                sol, success = torch.linalg.solve_ex(self.H, -self.b) # pylint:disable=not-callable
                if success: self.min_value = 0.5*(sol @ self.H).dot(sol) + sol.dot(self.b)
            except Exception:
                pass


    def get_loss(self):
        x = self.x + self.target

        xH = algebras.matmul(x, self.H, self.algebra)
        xHx = algebras.dot(xH, x, self.algebra)
        xb = algebras.dot(x, self.b, self.algebra)

        loss = 0.5*xHx + xb
        if self.min_value is not None: return loss - self.min_value
        return loss


class Rosenbrock(Benchmark):
    """rosenbrock"""
    def __init__(self, dim=512, variant:Literal[1,2]=1, ):
        super().__init__()
        self.x = torch.nn.Parameter(torch.tensor([-1.2, 1.]).repeat(dim//2))
        self.variant = variant

    def get_loss(self):
        if self.variant == 1:
            x1 = self.x[:-1]
            x2 = self.x[1:]

        elif self.variant == 2:
            x1 = self.x[:-1:2]
            x2 = self.x[1::2]

        else: raise ValueError(self.variant)

        return (100 * (x2 - x1**2)**2 + (1 - x1)**2).mean()


class ChebushevRosenbrock(Benchmark):
    """https://cs.nyu.edu/~overton/g22_ns_opt/CourseLastLecture.pdf"""
    def __init__(self, dim=512, p=8, variant:Literal[1,2]=1, max=False):
        super().__init__()
        self.x = torch.nn.Parameter(torch.tensor([-1.2, 1.]).repeat(dim//2))
        self.p = p
        self.variant = variant
        self.max = max

    def get_loss(self):
        x1 = self.x[:-1]
        x2 = self.x[1:]
        term1 = 1/4 * (self.x[0] - 1)**2

        if self.variant == 1: xp = x1**2
        elif self.variant == 2: xp = x1.abs()
        else: raise ValueError(self.variant)

        term2 = (x2 - 2*xp + 1).abs().pow(self.p).sum()

        if self.max: return term1.maximum(term2)
        return term1 + term2


class IllConditioned(Benchmark):
    """the diabolical hessian looks like this

    .. code:: py

        tensor([[2, c, c, c],
                [c, 2, c, c],
                [c, c, 2, c],
                [c, c, c, 2]])

    condition number is (2 + c(dim-1)) / (2 - c)
    """
    def __init__(self, dim=512, c=1.9999, seed=0):
        super().__init__(seed=seed)
        generator = self.rng.torch()

        self.x = torch.nn.Parameter(torch.randn(dim, generator=generator))
        self.c = c
        self.b = torch.nn.Buffer(torch.randn(dim, generator=generator, requires_grad=False))


    def get_loss(self):
        x = self.x + self.b; c = self.c

        susq = torch.sum(x**2)
        sum = torch.sum(x)
        term1 = 1.0 - 0.5 * c
        term2 = 0.5 * c

        return term1 * susq + term2 * (sum**2)


# this is from https://github.com/konstmish/opt_methods/tree/master/optmethods/loss
class LogSumExp(Benchmark):
    def __init__(self, n:int=1024, dim:int=512, smoothing=1, lstsq_term=False, l2=0):
        super().__init__()
        self.smoothing = smoothing
        self.lstsq_term = lstsq_term
        self.n, self.dim = n, dim
        self.l2 = l2

        self.x = nn.Parameter(torch.randn(dim, generator=self.rng.torch()))

        self.b = nn.Buffer(torch.normal(-1, 1, size=(n,), generator=self.rng.torch()))
        A = torch.empty((n, dim)).uniform_(-1, 1, generator=self.rng.torch())
        self.A = nn.Buffer(A)

    def get_loss(self):
        Ax = self.A @ self.x

        regularization = 0

        if self.l2 != 0:
            regularization = self.l2/2 * self.x.dot(self.x)

        if self.lstsq_term:
            regularization += 1/2 * Ax.dot(Ax)

        return (self.smoothing * torch.logsumexp(((Ax-self.b)/self.smoothing), 0)).abs() + regularization
