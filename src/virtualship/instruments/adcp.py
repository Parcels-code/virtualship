"""ADCP instrument."""

from pathlib import Path

import numpy as np
from parcels import FieldSet, Particle, ParticleSet, Variable

from virtualship.models import Spacetime

_ADCPParticle = Particle.add_variable(
    [
        Variable("U", dtype=np.float32, initial=np.nan),
        Variable("V", dtype=np.float32, initial=np.nan),
    ]
)


def _sample_velocity(particles, fieldset):
    particles.U, particles.V = fieldset.UV.eval(
        particles.time,
        particles.z,
        particles.lat,
        particles.lon,
        applyConversion=False,
    )


def simulate_adcp(
    fieldset: FieldSet,
    out_path: str | Path,
    max_depth: float,
    min_depth: float,
    num_bins: int,
    sample_points: list[Spacetime],
) -> None:
    """
    Use Parcels to simulate an ADCP in a fieldset.

    :param fieldset: The fieldset to simulate the ADCP in.
    :param out_path: The path to write the results to.
    :param max_depth: Maximum depth the ADCP can measure.
    :param min_depth: Minimum depth the ADCP can measure.
    :param num_bins: How many samples to take in the complete range between max_depth and min_depth.
    :param sample_points: The places and times to sample at.
    """
    sample_points.sort(key=lambda p: p.time)

    bins = np.linspace(max_depth, min_depth, num_bins)
    num_particles = len(bins)
    particleset = ParticleSet.from_list(
        fieldset=fieldset,
        pclass=_ADCPParticle,
        lon=np.full(
            num_particles, 0.0
        ),  # initial lat/lon are irrelevant and will be overruled later.
        lat=np.full(num_particles, 0.0),
        depth=bins,
        time=0,  # same for time
    )

    # define output file for the simulation
    # outputdt set to infinite as we just want to write at the end of every call to 'execute'
    out_file = particleset.ParticleFile(name=out_path, outputdt=np.inf)

    for point in sample_points:
        particleset.lon_nextloop[:] = point.location.lon
        particleset.lat_nextloop[:] = point.location.lat
        particleset.time_nextloop[:] = fieldset.time_origin.reltime(
            np.datetime64(point.time)
        )

        # perform one step using the particleset
        # dt and runtime are set so exactly one step is made.
        particleset.execute(
            [_sample_velocity],
            dt=1,
            runtime=1,
            verbose_progress=False,
            output_file=out_file,
        )
