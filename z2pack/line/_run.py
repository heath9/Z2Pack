#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author:  Dominik Gresch <greschd@gmx.ch>
# Date:    12.02.2016 16:04:45 CET
# File:    _run.py

import time
import contextlib

import numpy as np
from fsc.export import export

from . import _LOGGER
from . import LineResult
from . import EigenstateLineData, WccLineData
from ._control import StepCounter, PosCheck, ForceFirstUpdate

from .._control import (
    StatefulControl,
    IterationControl,
    DataControl,
    ConvergenceControl,
    LineControl
)

from .._logging_tools import TagAdapter

# tag which triggers filtering when called from the surface's run.
LINE_ONLY__LOGGER = TagAdapter(_LOGGER, default_tags=('line', 'line_only',))
_LOGGER = TagAdapter(_LOGGER, default_tags=('line',))

@export
def run_line(
        *,
        system,
        line,
        iterator=range(8, 27, 2),
        pos_tol=1e-2,
        save_file=None,
        init_result=None,
        load=False,
        load_quiet=True,
        serializer='auto'
):
    """
    Wrapper for:
        * getting / disecting old result
        * setting up Controls
            - from old result -> to impl?
            - from input parameters
        * setting up result -> to impl?
        * setting up printing status
        * setting up file backend
    """

    LINE_ONLY__LOGGER.info(locals(), tags=('setup', 'box', 'skip'))
    # This is here to avoid circular import with the Surface (is solved in Python 3.5 and higher)
    
    from .. import io

    # setting up controls
    controls = []
    controls.append(StepCounter(iterator=iterator))
    if pos_tol is None:
        controls.append(ForceFirstUpdate())
    else:
        controls.append(PosCheck(pos_tol=pos_tol))

    # setting up init_result
    if init_result is not None:
        if load:
            raise ValueError('Inconsistent input parameters "init_result != None" and "load == True". Cannot decide whether to load result from file or use given result.')
    elif load:
        if save_file is None:
            raise ValueError('Cannot load result from file: No filename given in the "save_file" parameter.')
        try:
            init_result = io.load(save_file, serializer=serializer)
        except IOError as e:
            if not load_quiet:
                raise e

    return _run_line_impl(*controls, system=system, line=line, save_file=save_file, init_result=init_result)


def _run_line_impl(
        *controls,
        system,
        line,
        save_file=None,
        init_result=None,
        serializer='auto'
):
    """
    Input parameters:
        * Controls
        * file backend?
    """
    # This is here to avoid circular import with the Surface (is solved in Python 3.5 and higher)
    from .. import io

    start_time = time.time() # timing the run

    for ctrl in controls:
        if not isinstance(ctrl, LineControl):
            raise ValueError('{} control object is not a LineControl instance.'.format(ctrl.__class__))

    def filter_ctrl(ctrl_type):
        return [ctrl for ctrl in controls if isinstance(ctrl, ctrl_type)]

    stateful_ctrl = filter_ctrl(StatefulControl)
    iteration_ctrl = filter_ctrl(IterationControl)
    data_ctrl = filter_ctrl(DataControl)
    convergence_ctrl = filter_ctrl(ConvergenceControl)

    def save():
        if save_file is not None:
            _LOGGER.info('Saving line result to file {}'.format(save_file))
            io.save(result, save_file, serializer=serializer)

    # initialize stateful and data controls from old result
    if init_result is not None:
        for d_ctrl in data_ctrl:
            # not necessary for StatefulControls
            if d_ctrl not in stateful_ctrl:
                d_ctrl.update(init_result.data)
        for s_ctrl in stateful_ctrl:
            with contextlib.suppress(KeyError):
                s_ctrl.state = init_result.ctrl_states[s_ctrl.__class__.__name__]
        result = LineResult(init_result.data, stateful_ctrl, convergence_ctrl)
        save()

    # Detect which type of System is active
    if hasattr(system, 'get_eig'):
        DataType = EigenstateLineData
        system_fct = system.get_eig
    else:
        DataType = WccLineData.from_overlaps
        system_fct = system.get_mmn

    def collect_convergence():
        res = [c_ctrl.converged for c_ctrl in convergence_ctrl]
        LINE_ONLY__LOGGER.info('{} of {} line convergence criteria fulfilled.'.format(sum(res), len(res)))
        return res

    # main loop
    while not all(collect_convergence()):
        run_options = dict()
        for it_ctrl in iteration_ctrl:
            try:
                run_options.update(next(it_ctrl))
                _LOGGER.info('Calculating line for N = {}'.format(run_options['num_steps']), tags=('offset',))
            except StopIteration:
                _LOGGER.warn('Iterator stopped before the calculation could converge.')
                return result

        data = DataType(system_fct(
            list(np.array(line(k)) for k in np.linspace(0., 1., run_options['num_steps']))
        ))

        for d_ctrl in data_ctrl:
            d_ctrl.update(data)

        result = LineResult(data, stateful_ctrl, convergence_ctrl)
        save()

    end_time = time.time()
    LINE_ONLY__LOGGER.info(end_time - start_time, tags=('box', 'skip-before', 'timing'))
    LINE_ONLY__LOGGER.info(result.convergence_report, tags=('convergence_report', 'box'))
    return result
