from argparse import ArgumentTypeError

import numpy as np
from scipy.optimize import linprog
from six.moves import range


def hessian(a, b, x):
    """Return log-barrier Hessian matrix at x."""
    d = (b - a.dot(x))
    s = d ** -2.0
    return a.T.dot(np.diag(s)).dot(a)


def local_norm(h, v):
    """Return the local norm of v based on the given Hessian matrix."""
    return v.T.dot(h).dot(v)


def sample_ellipsoid(e, r):
    """Return a point in the (hyper)ellipsoid uniformly sampled.
    The ellipsoid is defined by the positive definite matrix, ``e``, and
    the radius, ``r``.
    """
    # Generate a point on the sphere surface
    p = np.random.normal(size=e.shape[0])
    p /= np.linalg.norm(p)

    # Scale to a point in the sphere volume
    p *= np.random.uniform() ** (1.0 / e.shape[0])

    # Transform to a point in the ellipsoid
    return np.sqrt(r) * np.linalg.cholesky(np.linalg.inv(e)).dot(p)


def ellipsoid_axes(e):
    """Return matrix with columns that are the axes of the ellipsoid."""
    w, v = np.linalg.eigh(e)
    return v.dot(np.diag(w ** (-1 / 2.0)))


def dikin_walk(a, b, x0, r=3 / 40):
    """Generate points with Dikin walk."""
    x = x0
    h_x = hessian(a, b, x)

    while True:
        if not (a.dot(x) <= b).all():
            print(a.dot(x) - b)
            raise Exception('Invalid state: {}'.format(x))

        if np.random.uniform() < 0.5:
            yield x
            continue

        z = x + sample_ellipsoid(h_x, r)
        h_z = hessian(a, b, z)

        if local_norm(h_z, x - z) > 1.0:
            yield x
            continue

        p = np.sqrt(np.linalg.det(h_z) / np.linalg.det(h_x))
        if p >= 1 or np.random.uniform() < p:
            x = z
            h_x = h_z

        yield x


def hit_and_run(a, b, x0):
    """Generate points with Hit-and-run algorithm."""
    x = x0

    while True:
        if not (a.dot(x) <= b).all():
            print(a.dot(x) - b)
            raise Exception('Invalid state: {}'.format(x))

        # Generate a point on the sphere surface
        d = np.random.normal(size=a.shape[1])
        d /= np.linalg.norm(d)

        # Find closest boundary in the direction
        dist = np.divide(b - a.dot(x), a.dot(d))
        closest = dist[dist > 0].min()

        x += d * closest * np.random.uniform()

        yield x


def chebyshev_center(a, b):
    """Return Chebyshev center of the convex polytope."""
    norm_vector = np.reshape(np.linalg.norm(a, axis=1), (a.shape[0], 1))
    c = np.zeros(a.shape[1] + 1)
    c[-1] = -1
    a_lp = np.hstack((a, norm_vector))
    res = linprog(c, A_ub=a_lp, b_ub=b, bounds=(None, None))
    if not res.success:
        raise Exception('Unable to find Chebyshev center')

    return res.x[:-1]


def collect_chain(sampler, count, burn, thin, *args, **kwargs):
    """Use the given sampler to collect points from a chain.
    Args:
        count: Number of points to collect.
        burn: Number of points to skip at beginning of chain.
        thin: Number of points to take from sampler for every point.
    """
    chain = sampler(*args, **kwargs)
    point = next(chain)
    points = np.empty((count, point.shape[0]))

    for i in range(burn - 1):
        next(chain)

    for i in range(count):
        points[i] = next(chain)
        for _ in range(thin - 1):
            next(chain)

    return points


def do_sample(leq, leq_rhs, count=100, burn=1000, thin=10, sampler='hit-and-run'):
    """Entry point."""
    # Find nullspace

    vh = np.identity(leq.shape[1])

    nullity = vh.shape[0]
    nullspace = vh[-nullity:].T

    # Polytope parameters
    a = leq.dot(nullspace)
    b = leq_rhs

    # Initial point to start the chains from.
    # Use the Chebyshev center.
    x0 = chebyshev_center(a, b)

    if sampler == 'dikin':
        sampler = dikin_walk
        dikin_radius = 1
        sampler_args = (dikin_radius,)
    elif sampler == 'hit-and-run':
        sampler = hit_and_run
        sampler_args = ()
    else:
        raise ArgumentTypeError('Invalid sampler: {}'.format(sampler))

    chain = collect_chain(sampler, count, burn, thin, a, b, x0, *sampler_args)
    res = chain.dot(nullspace.T)

    return res
