#!/usr/bin/env python
import sys

sys.path.insert(0, '..')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import json
from scipy.stats import gaussian_kde
import os

from model_specific_helpers import (
    get_example_site_vars,
    make_param_filter_func,
    # make_weighted_cost_func,
    make_param2res,
    # make_param2res_2,
    UnEstimatedParameters,
    EstimatedParameters,
    Observables
)

from general_helpers import (
    make_uniform_proposer,
    make_multivariate_normal_proposer,
    mcmc,
    adaptive_mcmc,
    autostep_mcmc,
    make_feng_cost_func,
    plot_solutions
)

with Path('config.json').open(mode='r') as f:
    conf_dict = json.load(f)

dataPath = Path(conf_dict['dataPath'])
'''
npp, C_leaf, C_wood, C_root, C_litter_above, C_litter_below, C_fast_som, C_slow_som, C_pass_som, \
rh, f_veg2litter, f_litter2som, mrso, tsl = get_example_site_vars(dataPath)
'''
npp, C_leaf, C_wood, C_root, C_litter_above, C_litter_below, C_slow_som, C_pass_som, \
rh, f_veg2litter, mrso, tsl = get_example_site_vars(dataPath)

#nyears = 150
nyears = 10  # reduced time span for testing purposes
tot_len = 12 * nyears
obs_tup = Observables(
    C_leaf=C_leaf,
    C_wood=C_wood,
    C_root=C_root,
    C_litter_above=C_litter_above,
    C_litter_below=C_litter_below,
    #C_fast_som=C_fast_som,
    C_slow_som=C_slow_som,
    C_pass_som=C_pass_som,
    rh=rh,
    f_veg2litter=f_veg2litter,
    #f_litter2som=f_litter2som
)
obs = np.stack(obs_tup, axis=1)[0:tot_len, :]

# save observational data for comparison with model output
#pd.DataFrame(obs).to_csv(dataPath.joinpath('obs.csv'), sep=',')

#LiangJY: write to a 'output' directory
parent_dir = os.getcwd()
output_dir = os.path.join(parent_dir,'output')
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

pd.DataFrame(obs).to_csv('output/obs.csv', sep=',')   #LiangJY for test

cpa = UnEstimatedParameters(
    C_leaf_0=C_leaf[0],
    C_wood_0=C_wood[0],
    C_root_0=C_root[0],
    C_litter_above_0=C_litter_above[0],
    C_litter_below_0=C_litter_below[0],
    #C_fast_som_0=C_fast_som[0],
    C_slow_som_0=C_slow_som[0],
    C_pass_som_0=C_pass_som[0],
    rh_0=rh[0],
    f_veg_lit_0=f_veg2litter[0],
    #f_lit_soil_0=f_litter2som[0],
    npp=npp,
    number_of_months=tot_len,
    mrso=mrso,
    tsl=tsl
)
param2res = make_param2res(cpa)

c_min = np.array(
    EstimatedParameters(
        beta_leaf=0.05,
        beta_wood=0.35,
        f_leaf2sur_met_lit=1e-3, #f4,1
        f_wood2sur_met_lit=1e-3, #f4,2
        f_root2root_str_lit=1e-3, #f6,3
        f_sur_met_lit2sur_mic=1e-3, #f8,4
        f_sur_str_lit2sur_mic=1e-3, #f8,5
        f_root_met_lit2soil_mic=1e-3, #f9,7
        f_root_str_lit2soil_mic=1e-3, #f9,6
        f_sur_str_lit2soil_slow=1e-3, #f10,5
        f_root_str_lit2soil_slow=1e-3, #f10,6
        f_sur_mic2soil_slow=1e-3, #f10,8
        f_soil_mic2soil_slow=1e-3, #f10,9
        f_soil_mic2soil_pass=1e-3, #f11,9
        f_soil_slow2soil_mic=1e-3, #f9,10
        f_soil_slow2soil_pass=1e-3, #f11,10
        f_soil_pass2soil_mic=1e-3, #f9,11
        k_leaf=1 / (365 * 2),
        k_wood=1 / (365 * 60),
        k_root=1 / (365 * 30),
        k_sur_met_lit=1 / (365 * 60),
        k_sur_str_lit=1 / (365 * 30),
        k_root_met_lit=1 / (365 * 60),
        k_root_str_lit=1 / (365 * 30),
        k_sur_mic=1 / (365 * 200),
        k_soil_mic=1 / (365 * 200),
        k_soil_slow=1 / (365 * 500),
        k_soil_pass=1 / (365 * 1000),
        f_sur_met_lit=0.1, #fraction of surface metabolic litter
        f_root_met_lit=0.1, #fraction of root metabolic litter
        C_sur_mic_0=0, #initial value of surface microbial C
        C_soil_mic_0=0, #initial value of soil microbial C
        T_0=-10,
        E=1,
        KM=1
    )
)

c_max = np.array(
    EstimatedParameters(
        beta_leaf=0.18,
        beta_wood=0.65,
        f_leaf2sur_met_lit=5e-1, #f4,1
        f_wood2sur_met_lit=5e-1, #f4,2
        f_root2root_str_lit=5e-1, #f6,3
        f_sur_met_lit2sur_mic=5e-1, #f8,4
        f_sur_str_lit2sur_mic=5e-1, #f8,5
        f_root_met_lit2soil_mic=5e-1, #f9,7
        f_root_str_lit2soil_mic=5e-1, #f9,6
        f_sur_str_lit2soil_slow=5e-1, #f10,5
        f_root_str_lit2soil_slow=5e-1, #f10,6
        f_sur_mic2soil_slow=5e-1, #f10,8
        f_soil_mic2soil_slow=5e-1, #f10,9
        f_soil_mic2soil_pass=5e-1, #f11,9
        f_soil_slow2soil_mic=5e-1, #f9,10
        f_soil_slow2soil_pass=5e-1, #f11,10
        f_soil_pass2soil_mic=5e-1, #f9,11
        k_leaf=1 / 30,
        k_wood=1 / (365 * 1),
        k_root=1 / (365 * 0.5),
        k_sur_met_lit=1 / (365 * 1),
        k_sur_str_lit=1 / (365 * 0.5),
        k_root_met_lit=1 / (365 * 1),
        k_root_str_lit=1 / (365 * 0.5),
        k_sur_mic=1 / (365 * 1),
        k_soil_mic=1 / (365 * 1),
        k_soil_slow=1 / (365 * 3.5),
        k_soil_pass=1 / (365 * 10),
        f_sur_met_lit=0.5, #fraction of surface metabolic litter
        f_root_met_lit=0.5, #fraction of root metabolic litter
        C_sur_mic_0=0.4, #initial value of surface microbial C
        C_soil_mic_0=0.4, #initial value of soil microbial C
        T_0=4,
        E=100,
        KM=100
    )
)
# I commented your original settings and instead used the
# values constructed from the limits (see below)
epa_0 = EstimatedParameters(
    beta_leaf=0.15,
        beta_wood=0.45,
        f_leaf2sur_met_lit=5e-3, #f4,1
        f_wood2sur_met_lit=5e-3, #f4,2
        f_root2root_str_lit=5e-3, #f6,3
        f_sur_met_lit2sur_mic=5e-3, #f8,4
        f_sur_str_lit2sur_mic=5e-3, #f8,5
        f_root_met_lit2soil_mic=5e-3, #f9,7
        f_root_str_lit2soil_mic=5e-3, #f9,6
        f_sur_str_lit2soil_slow=5e-3, #f10,5
        f_root_str_lit2soil_slow=5e-3, #f10,6
        f_sur_mic2soil_slow=5e-3, #f10,8
        f_soil_mic2soil_slow=5e-3, #f10,9
        f_soil_mic2soil_pass=5e-3, #f11,9
        f_soil_slow2soil_mic=5e-3, #f9,10
        f_soil_slow2soil_pass=5e-3, #f11,10
        f_soil_pass2soil_mic=5e-3, #f9,11
        k_leaf=1 / (365 * 1),
        k_wood=1 / (365 * 30),
        k_root=1 / (365 * 20),
        k_sur_met_lit=1 / (365 * 30),
        k_sur_str_lit=1 / (365 * 20),
        k_root_met_lit=1 / (365 * 30),
        k_root_str_lit=1 / (365 * 20),
        k_sur_mic=1 / (365 * 100),
        k_soil_mic=1 / (365 * 100),
        k_soil_slow=1 / (365 * 100),
        k_soil_pass=1 / (365 * 100),
        f_sur_met_lit=0.2, #fraction of surface metabolic litter
        f_root_met_lit=0.2, #fraction of root metabolic litter
        C_sur_mic_0=0.1, #initial value of surface microbial C
        C_soil_mic_0=0.1, #initial value of soil microbial C
        T_0=0,
        E=10,
        KM=10
)
# save initial parameters
#pd.DataFrame(epa_0).to_csv(dataPath.joinpath('epa_0.csv'), sep=',')
pd.DataFrame(epa_0).to_csv('output/pa_0.csv', sep=',')   #LiangJY for test

# epa_0 = EstimatedParameters._make(
#         np.concatenate(
#             [
#                 # we don't want to use the average for
#                 # the betas and fs since their sum will immediately
#                 # violate our filter condition 3,4,5,6
#                 np.array((0.25, 0.2, 0.42,0.075, 0.005, 0.35, 0.12,  0.03, 0.37, 0.11, 0.01)),
#                 # but for the rest it se
#                 (c_min+c_max)[11:] / 2.0
#             ]
#         )
# )

isQualified = make_param_filter_func(c_max, c_min)
# check if the current value passes the filter
# to avoid to get stuck in an inescapable series of rejections
if not (isQualified(np.array(epa_0))):
    raise ValueError(
        """the current value does not pass filter_func. This is probably due to an initial value chosen outside the permitted range""")

# Autostep MCMC: with uniform proposer modifying its step every 100 iterations depending on acceptance rate
C_autostep, J_autostep = autostep_mcmc(
    initial_parameters=epa_0,
    filter_func=isQualified,
    param2res=param2res,
    costfunction=make_feng_cost_func(obs),
    nsimu=10000,
    c_max=c_max,
    c_min=c_min,
    acceptance_rate=10,   # default value | target acceptance rate in %
    chunk_size=100,  # default value | number of iterations to calculate current acceptance ratio and update step size
    D_init=1   # default value | increase value to reduce initial step size
)
# save the parameters and cost function values for postprocessing
'''
pd.DataFrame(C_autostep).to_csv(dataPath.joinpath('bcc_autostep_da_aa.csv'), sep=',')
pd.DataFrame(J_autostep).to_csv(dataPath.joinpath('bcc_autostep_da_j_aa.csv'), sep=',')
'''
pd.DataFrame(C_autostep).to_csv('output/bcc_autostep_da_aa.csv', sep=',')
pd.DataFrame(J_autostep).to_csv('output/bcc_autostep_da_j_aa.csv', sep=',')


# calculate maximum likelihood for each parameter as a peak of posterior distribution
def density_peaks(distr):
    peaks = np.zeros(distr.shape[0])
    for i in range(distr.shape[0]):
        x = distr[i, :]
        pdf = gaussian_kde(x)
        l = np.linspace(np.min(x), np.max(x), len(x))
        density = pdf(l)
        peaks[i] = l[density.argmax()]
    return peaks

max_likelihood_autostep = density_peaks(C_autostep)

# forward run with median, max likelihood, and min J parameter sets
sol_median_autostep = param2res(np.median(C_autostep, axis=1))
sol_likelihood_autostep = param2res(max_likelihood_autostep)
sol_min_J_autostep = param2res(C_autostep[:, np.where(J_autostep[1] == np.min(J_autostep[1]))])
# export solutions
'''
pd.DataFrame(sol_median_autostep).to_csv(dataPath.joinpath('sol_median_autostep.csv'), sep=',')
pd.DataFrame(sol_likelihood_autostep).to_csv(dataPath.joinpath('sol_likelihood_autostep.csv'), sep=',')
pd.DataFrame(sol_min_J_autostep).to_csv(dataPath.joinpath('sol_min_J_autostep.csv'), sep=',')
'''
pd.DataFrame(sol_median_autostep).to_csv('output/sol_median_autostep.csv', sep=',')
pd.DataFrame(sol_likelihood_autostep).to_csv('output/sol_likelihood_autostep.csv', sep=',')
pd.DataFrame(sol_min_J_autostep).to_csv('output/sol_min_J_autostep.csv', sep=',')

# Demo MCMC: with a uniform proposer and fixed step
uniform_prop = make_uniform_proposer(
    c_min,
    c_max,
    D=240,
    filter_func=isQualified
)

C_demo, J_demo = mcmc(
    initial_parameters=epa_0,
    proposer=uniform_prop,
    param2res=param2res,
    # costfunction=make_weighted_cost_func(obs)
    costfunction=make_feng_cost_func(obs),
    nsimu=10000
)
# save the parameters and cost function values for postprocessing
'''
pd.DataFrame(C_demo).to_csv(dataPath.joinpath('bcc_demo_da_aa.csv'), sep=',')
pd.DataFrame(J_demo).to_csv(dataPath.joinpath('bcc_demo_da_j_aa.csv'), sep=',')
'''
pd.DataFrame(C_demo).to_csv('output/bcc_demo_da_aa.csv', sep=',')
pd.DataFrame(J_demo).to_csv('output/bcc_demo_da_j_aa.csv', sep=',')

max_likelihood_demo = density_peaks(C_demo)

# forward run with median, max likelihood, and min J parameter sets
sol_median_demo = param2res(np.median(C_demo, axis=1))
sol_likelihood_demo = param2res(max_likelihood_demo)
sol_min_J_demo = param2res(C_demo[:, np.where(J_demo[1] == np.min(J_demo[1]))])
# export solutions
'''
pd.DataFrame(sol_median_demo).to_csv(dataPath.joinpath('sol_median_demo.csv'), sep=',')
pd.DataFrame(sol_likelihood_demo).to_csv(dataPath.joinpath('sol_likelihood_demo.csv'), sep=',')
pd.DataFrame(sol_min_J_demo).to_csv(dataPath.joinpath('sol_min_J_demo.csv'), sep=',')
'''
pd.DataFrame(sol_median_demo).to_csv('output/sol_median_demo.csv', sep=',')
pd.DataFrame(sol_likelihood_demo).to_csv('output/sol_likelihood_demo.csv', sep=',')
pd.DataFrame(sol_min_J_demo).to_csv('output/sol_min_J_demo.csv', sep=',')

# build a new proposer based on a multivariate_normal distribution using the estimated covariance of the previous run if available
# parameter values of the previous run

# Formal MCMC: with multivariate normal proposer based on adaptive covariance matrix
C_formal, J_formal = adaptive_mcmc(
    initial_parameters=epa_0,
    covv=np.cov(C_demo[:, int(C_demo.shape[1] / 10):]),
    filter_func=isQualified,
    param2res=param2res,
    # costfunction=make_weighted_cost_func(obs)
    costfunction=make_feng_cost_func(obs),
    nsimu=10000,
    sd_controlling_factor=1  # default value | increase value to reduce step size
)
# save the parameters and cost function values for postprocessing
'''
pd.DataFrame(C_formal).to_csv(dataPath.joinpath('bcc_formal_da_aa.csv'), sep=',')
pd.DataFrame(J_formal).to_csv(dataPath.joinpath('bcc_formal_da_j_aa.csv'), sep=',')
'''
pd.DataFrame(C_formal).to_csv('output/bcc_formal_da_aa.csv', sep=',')
pd.DataFrame(J_formal).to_csv('output/bcc_formal_da_j_aa.csv', sep=',')

max_likelihood_formal = density_peaks(C_formal)
# forward run with median, max likelihood, and min J parameter sets
sol_median_formal = param2res(np.median(C_formal, axis=1))
sol_likelihood_formal = param2res(max_likelihood_formal)
sol_min_J_formal = param2res(C_formal[:, np.where(J_formal[1] == np.min(J_formal[1]))])
# export solutions
'''
pd.DataFrame(sol_median_formal).to_csv(dataPath.joinpath('sol_median_formal.csv'), sep=',')
pd.DataFrame(sol_likelihood_formal).to_csv(dataPath.joinpath('sol_likelihood_formal.csv'), sep=',')
pd.DataFrame(sol_min_J_formal).to_csv(dataPath.joinpath('sol_min_J_formal.csv'), sep=',')
'''
pd.DataFrame(sol_median_formal).to_csv('output/sol_median_formal.csv', sep=',')
pd.DataFrame(sol_likelihood_formal).to_csv('output/sol_likelihood_formal.csv', sep=',')
pd.DataFrame(sol_min_J_formal).to_csv('output/sol_min_J_formal.csv', sep=',')

# POSTPROCESSING
#
# The 'solution' of the inverse problem is actually the (joint) posterior
# probability distribution of the parameters, which we approximate by the
# histogram consisting of the mcmc generated samples.
# This joint distribution contains as much information as all its (infinitely
# many) projections to curves through the parameter space combined.
# Unfortunately, for this very reason, a joint distribution of more than two
# parameters is very difficult to visualize in its entirety.
# to do:
#   a) make a movie of color coded samples  of the a priori distribution of the parameters.
#   b) -"-                                  of the a posterior distribution -'-

# Therefore the  following visualizations have to be considered with caution:
# 1.
# The (usual) histograms of the values of a SINGLE parameters can be very
# misleading since e.g. we can not see that certain parameter combination only
# occure together. In fact this decomposition is only appropriate for
# INDEPENDENT distributions of parameters in which case the joint distribution
# would be the product of the distributions of the single parameters.  This is
# however not even to be expected if our prior probability distribution can be
# decomposed in this way. (Due to the fact that the Metropolis Hastings Alg. does not
# produce independent samples )

# df = pd.DataFrame({name: C_formal[:, i] for i, name in enumerate(EstimatedParameters._fields)})
# subplots = df.hist()
# fig = subplots[0, 0].figure
# fig.set_figwidth(15)
# fig.set_figheight(15)
# fig.savefig('histograms.pdf')

# As the next best thing we can create a matrix of plots containing all
# projections to possible  parameter tuples
# (like the pairs plot in the R package FME) but 16x16 plots are too much for one page..
# However the plot shows that we are dealing with a lot of collinearity for this  parameter set

# subplots = pd.plotting.scatter_matrix(df)
# fig = subplots[0, 0].figure
# fig.set_figwidth(15)
# fig.set_figheight(15)
# fig.savefig('scatter_matrix.pdf')

# 2.
# another way to get an idea of the quality of the parameter estimation is
# to plot trajectories.
# A possible aggregation of this histogram to a singe parameter
# vector is the mean which is an estimator of  the expected value of the
# desired distribution.

# fig = plt.figure()
# plot_solutions(
#     fig,
#     times=range(sol_median_formal.shape[0]),
#     var_names=Observables._fields,
#     tup=(sol_median_formal, obs),
#     names=('mean', 'obs')
# )
# fig.savefig('solutions.pdf')

