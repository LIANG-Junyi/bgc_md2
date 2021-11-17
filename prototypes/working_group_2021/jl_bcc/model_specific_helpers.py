import pathlib
from typing import Callable
import netCDF4 as nc
import numpy as np
from collections import namedtuple
from functools import reduce
from general_helpers import day_2_month_index, month_2_day_index, months_by_day_arr, TimeStepIterator2, respiration_from_compartmental_matrix

# fixme:
# Your parameters will most likely differ but you can still use the
# destinctions between different sets of parameters. The aim is to make
# the different tasks in the code more obvious. In principal you could
# have a lot of overlapping sets and just have to keep them consistent. 
# 'namedtuples' can be used just as normal tuples by functions
# that are not aware of the names. They can still use the positions like 
# in the original code

# This set is used by the functions that produce the
# specific ingredients (functions) that will be run by
# mcmc alg.
UnEstimatedParameters = namedtuple(
    "UnEstimatedParameters",
    [
        'C_leaf_0',
        'C_wood_0',
        'C_root_0',
        'C_litter_above_0',
        'C_litter_below_0',
        #'C_fast_som_0',   #LiangJY
        'C_slow_som_0',
        'C_pass_som_0',
        'rh_0',
        'f_veg_lit_0',
        #'f_lit_soil_0',   #LiangJY
        'npp',
        'number_of_months',
        'mrso',
        'tsl'
    ]
)

# This set is used (as argument) by the functions that are called
# inside the mcmc
EstimatedParameters = namedtuple(
    "EstiamatedParameters",
    [
        "beta_leaf",    #  0 (indices uses in original code) 
        "beta_wood",    #  1
        "f_leaf2sur_met_lit", #f4,1
        #"f_leaf2sur_str_lit", #f5,1=1-f4,1
        "f_wood2sur_met_lit", #f4,2
        #"f_wood2sur_str_lit", #f5,2=1-f4,2
        "f_root2root_str_lit", #f6,3
        #"f_root2root_met_lit", #f7,3=1-f6,3
        "f_sur_met_lit2sur_mic", #f8,4
        "f_sur_str_lit2sur_mic", #f8,5
        "f_root_met_lit2soil_mic", #f9,7
        "f_root_str_lit2soil_mic", #f9,6
        "f_sur_str_lit2soil_slow", #f10,5
        "f_root_str_lit2soil_slow", #f10,6
        "f_sur_mic2soil_slow", #f10,8
        "f_soil_mic2soil_slow", #f10,9
        "f_soil_mic2soil_pass", #f11,9
        "f_soil_slow2soil_mic", #f9,10
        "f_soil_slow2soil_pass", #f11,10
        "f_soil_pass2soil_mic", #f9,11
        "k_leaf",       #  11
        "k_wood",       #  12
        "k_root",       #  13
        "k_sur_met_lit",
        "k_sur_str_lit",
        "k_root_met_lit",
        "k_root_str_lit",
        "k_sur_mic",
        "k_soil_mic",
        "k_soil_slow",
        "k_soil_pass",
        "f_sur_met_lit", #fraction of surface metabolic litter
        "f_root_met_lit", #fraction of root metabolic litter
        "C_sur_mic_0", #initial value of surface microbial C
        "C_soil_mic_0", #initial value of soil microbial C
        "T_0",	# 21
        "E",	# 22
        "KM"    # 23
    ]
)

# This is the set off all 
_Parameters = namedtuple(
        "Parameters",
        EstimatedParameters._fields + UnEstimatedParameters._fields
)
class Parameters(_Parameters):
    @classmethod
    def from_EstimatedParametersAndUnEstimatedParameters(
            cls,
            epa :EstimatedParameters,
            cpa :UnEstimatedParameters
        ):
        return cls(*(epa + cpa))


# This set defines the order of the c pools
# The order is crucial for the compatibility
# with the matrices (B and b) If you change ist
# the matrix changes
StateVariables = namedtuple(
    'StateVariables',
    [
        'C_leaf',
        'C_wood',
        'C_root',
        'C_sur_met_lit',
        'C_sur_str_lit',
        'C_root_str_lit',
        'C_root_met_lit',
        'C_sur_mic',
        'C_soil_mic',
        'C_soil_slow',
        'C_soil_pass'
    ]
)
Observables = namedtuple(
    'Observables',
    [
        'C_leaf',
        'C_wood',
        'C_root',
        'C_litter_above',
        'C_litter_below',
        #'C_fast_som',
        'C_slow_som',
        'C_pass_som',
        'rh',
        'f_veg2litter',
        #'f_litter2som'
    ]
)

# We define another set of parameters which describes
# the parameters of the matrices A,K and the vector b
# and drivers like npp (in form of arrays)
# but does not include start values and hyperparameters like the 'number_of_months'
# This distinction is helpful for the forward simulation where the
# distinction between estimated and constant is irrelevant.
ModelParameters = namedtuple(
    "ModelParameters",
    [
        name for name in Parameters._fields 
        if name not in [
            'C_leaf_0',
            'C_wood_0',
            'C_root_0',
            'C_litter_above_0',
            'C_litter_below_0',
            'C_fast_som_0',
            'C_slow_som_0',
            'C_pass_som_0',
            'C_leaf_lit_0',
            'rh_0',
            'f_veg_lit_0',
            #'f_lit_soil_0'
            'number_of_months'
        ] 
    ]
)
# to do
# 1.) make a namedtuple for the yycable data or use xarray to create a multifile dataset
def get_variables_from_files(dataPath):
    # Read NetCDF data  ******************************************************************************************************************************
    names = [
        ('cLeaf', 'cLeaf_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        ('cLitterAbove', 'cLitterAbove_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        ('cLitterBelow', 'cLitterBelow_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        ('cRoot', 'cRoot_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        #('cSoilFast', 'cSoilFast_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f2_gn_185001-199912.nc'),
        ('cSoilMedium', 'cSoilMedium_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        ('cSoilSlow', 'cSoilSlow_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        ('cVeg', 'cVeg_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        #('fLitterSoil', 'fLitterSoil_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f2_gn_185001-199912.nc'),
        ('fVegLitter', 'fVegLitter_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        ('mrsos', 'mrsos_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        ('npp', 'npp_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        ('rh', 'rh_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_185001-199912.nc'),
        ('tsl', 'tsl_Lmon_BCC-CSM2-MR_1pctCO2-bgc_r1i1p1f1_gn_*.nc'),
    ]
    def f(tup):
        vn, fn = tup
        path = dataPath.joinpath(fn)
        #ds = nc.Dataset(str(path))
        ds = nc.MFDataset(str(path),'r')   #LiangJY read multiple files for one variable
        return ds.variables[vn][:, :, :]

    return map(f, names)

#     # Read NetCDF data  ******************************************************************************************************************************

def get_example_site_vars(dataPath):
    (
        C_leaf,
        C_litter_above,
        C_litter_below,
        C_root,
        #C_fast_som,
        C_slow_som,
        C_pass_som,
        C_veg,
        #f_litter2som,
        f_veg2litter,
        mrso,
        npp,
        rh,
        tsl
    )= get_variables_from_files(dataPath)
    # pick up 1 site   wombat state forest
    s = slice(None, None, None)  # this is the same as :
    #t = s, 50, 33  # [t] = [:,49,325]
    t = s, 80, 20  #LiangJY  # [t] = [:,49,325]
    npp = npp[t] * 86400   # kg/m2/s kg/m2/day;
    rh = rh[t]*86400  # per s to per day
    f_veg2litter = f_veg2litter[t] * 86400
    #f_litter2som = f_litter2som[t] * 86400
    #f_litter2som = f_veg2litter   #LiangJY for test
    #C_fast_som = C_slow_som/100  #LiangJY for test
    tsl_mean = np.mean(tsl, axis=1)  # average soil temperature at different depth
    (
        C_leaf,
        C_litter_above,
        C_litter_below,
        C_root,
        #C_fast_som,
        C_slow_som,
        C_pass_som,
        C_veg,
        mrso,
        tsl
    ) = map(
        lambda var: var[t],
        (
            C_leaf,
            C_litter_above,
            C_litter_below,
            C_root,
            #C_fast_som,
            C_slow_som,
            C_pass_som,
            C_veg,
            mrso,
            tsl_mean
        )
    )
    C_wood = C_veg - C_leaf - C_root
    
    '''
    return (npp, C_leaf, C_wood, C_root, C_litter_above, C_litter_below, C_fast_som, C_slow_som, C_pass_som,
            rh, f_veg2litter, f_litter2som, mrso, tsl)
    '''
    return (npp, C_leaf, C_wood, C_root, C_litter_above, C_litter_below, C_slow_som, C_pass_som,
            rh, f_veg2litter, mrso, tsl)
    
def make_param_filter_func(
        c_max: np.ndarray,
        c_min: np.ndarray
        ) -> Callable[[np.ndarray], bool]:

    def isQualified(c):
        # fixme
        #   this function is model specific: It discards parameter proposals
        #   where beta1 and beta2 are >0.99
        cond1 =  (c >= c_min).all() 
        cond2 =  (c <= c_max).all() 
        cond3 = (c[0] + c[1]) < 1
        cond4 = (c[2] + c[3] + c[4]) < 1
        cond5 = (c[5] + c[6] + c[7]) < 1
        cond6 = (c[8] + c[9] + c[10]) < 1
        return (cond1 and cond2 and cond3 and cond4 and cond5 and cond6)
        
    
    return isQualified

# def make_weighted_cost_func(
#         obs: np.ndarray
#     ) -> Callable[[np.ndarray],np.float64]:
#     # first unpack the observation array into its parts
#     cleaf, croot, cwood, clitter, csoil, rh = np.split(obs,indices_or_sections=6,axis=1)
#     def costfunction(out_simu: np.ndarray) ->np.float64:
#         # fixme
#         #   as indicated by the fact that the function lives in this
#         #   model-specific module it is not apropriate for (all) other models.
#         #   There are model specific properties:
#         #   1.) The weight for the different observation streams
#         #
#         tot_len=out_simu.shape[0]
#         # we assume the model output to be in the same shape and order
#         # as the obeservation
#         # this convention has to be honored by the forwar_simulation as well
#         # which in this instance already compresses the 3 different litter pools
#         # to c_litter and the 3 different soil pools to one
#         c_simu = out_simu[:,0:5]
#
#         # we assume the rh  part to be in the remaining columns again
#         # this convention has to be honored by the forwar_simulation as well
#         rh_simu = out_simu[:,5:]
#         #from IPython import embed; embed()
#
#         J_obj1 = np.mean (( c_simu[:,0] - cleaf[0:tot_len] )**2)/(2*np.var(cleaf[0:tot_len]))
#         J_obj2 = np.mean (( c_simu[:,1] - croot[0:tot_len] )**2)/(2*np.var(croot[0:tot_len]))
#         J_obj3 = np.mean (( c_simu[:,2] - cwood[0:tot_len] )**2)/(2*np.var(cwood[0:tot_len]))
#         J_obj4 = np.mean (( c_simu[:,3]-  clitter[0:tot_len] )**2)/(2*np.var(clitter[0:tot_len]))
#         J_obj5 = np.mean (( c_simu[:,4]-  csoil[0:tot_len] )**2)/(2*np.var(csoil[0:tot_len]))
#
#         J_obj6 = np.mean (( rh_simu[:,0] - rh[0:tot_len] )**2)/(2*np.var(rh[0:tot_len]))
#
#         J_new = (J_obj1 + J_obj2 + J_obj3 + J_obj4 + J_obj5 )/200+ J_obj6/4
#         return J_new
#     return costfunction


def make_param2res(
        cpa
    ) -> Callable[[np.ndarray], np.ndarray]: 
    """The returned function 'param2res' is used by the metropolis hastings algorithm
    to produce a result from a proposed parameter(tuple).
    'param2res' will be called only with the parameters to be estimated 'pe'.
    The constant parameters are the parameters of the present function 'pc' and are automatically
    available in the returned 'param2res' (closure).
    
    In the case of this model 'param2res' has to perform the following 
    tasks.
    -   use both sets of parameters 'pc' and 'pe' to build a forward model
    -   run the forward model to produce output for the times 
        when observations are available.(Here monthly)
    -   project the output of the forward model to the observed variables.
        (here summation of all different soil-pools to compare to the single
        observed soil-pool and the same for the litter pools)
        
    In this version of the function all tasks are performed at once as in 
    the original script.
    See the alternative implementation to see how all the tasks can be 
    delegated to smaller functions.
    """
    # fixme
    # This function is model-specific in several ways:
    # 0. Which are the fixed and which are the estimated variables
    # 1. The matrices for the forward simulation 
    # 2. the driver (here monthly npp)
    # 3. the projection of the simulated pool values to observable variables
    #    (here summation of   
    def param2res(pa):
        # pa is a numpy array when pa comes from the predictor
        # so we transform it to be able to use names instead of positions 
        epa = EstimatedParameters(*pa)
        days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        # Construct b vector 
        beta1 = epa.beta_leaf; beta2 = epa.beta_wood; beta3 = 1 - beta1 - beta2
        b = np.array([beta1, beta2, beta3, 0, 0, 0, 0, 0, 0, 0, 0]).reshape([11, 1])   # allocation
        # Now construct A matrix

        f41 = epa.f_leaf2sur_met_lit;
        f51 = 1-f41;
        f42 = epa.f_wood2sur_met_lit;
        f52 = 1-f42;
        f63 = epa.f_root2root_str_lit;
        f73 = 1-f63;
        f84 = epa.f_sur_met_lit2sur_mic;
        f85 = epa.f_sur_str_lit2sur_mic;
        f105 = epa.f_sur_str_lit2soil_slow;
        f96 = epa.f_root_str_lit2soil_mic;
        f106 = epa.f_root_str_lit2soil_slow;
        f97 = epa.f_root_met_lit2soil_mic;
        f108 = epa.f_sur_mic2soil_slow;
        f109 = epa.f_soil_mic2soil_slow;
        f119 = epa.f_soil_mic2soil_pass;
        f910 = epa.f_soil_slow2soil_mic;
        f1110 = epa.f_soil_slow2soil_pass;
        f911 = epa.f_soil_pass2soil_mic;
        
        A = np.array([  -1,   0,   0,   0,   0,   0,   0,   0,   0,    0,  0,
                         0,  -1,   0,   0,   0,   0,   0,   0,   0,    0,  0,
                         0,   0,  -1,   0,   0,   0,   0,   0,   0,    0,  0,
                       f41, f42,   0,  -1,   0,   0,   0,   0,   0,    0,  0,
                       f51, f52,   0,   0,  -1,   0,   0,   0,   0,    0,  0,
                         0,   0, f63,   0,   0,  -1,   0,   0,   0,    0,  0,
                         0,   0, f73,   0,   0,   0,  -1,   0,   0,    0,  0,
                         0,   0,   0, f84, f85,   0,   0,  -1,   0,    0,  0,
                         0,   0,   0,   0,   0, f96, f97,   0,  -1, f910,f911,
                         0,   0,   0,   0,f105,f106,   0,f108,f109,   -1,  0,
                         0,   0,   0,   0,   0,   0,   0,   0,f119,f1110, -1]).reshape([11, 11])   # transfer
    
        #turnover rate per day of pools: 
        temp = [epa.k_leaf, epa.k_wood, epa.k_root, 
                epa.k_sur_met_lit, epa.k_sur_str_lit,
                epa.k_root_str_lit, epa.k_root_met_lit,
                epa.k_sur_mic, epa.k_soil_mic,
                epa.k_soil_slow, epa.k_soil_pass]
        K = np.zeros(121).reshape([11, 11])
        for i in range(0, 11):
            K[i][i] = temp[i]
          
        x_fin=np.zeros((cpa.number_of_months,11))
        rh_fin=np.zeros((cpa.number_of_months,1))
        f_veg_lit_fin = np.zeros((cpa.number_of_months, 1))
        #f_lit_som_fin = np.zeros((cpa.number_of_months, 1))
        # leaf, root , wood, metabolic, structural, CWD, microbial, slow, passive 
        
        x_init = np.array(
            [
                cpa.C_leaf_0,
                cpa.C_wood_0,
                cpa.C_root_0,
                cpa.C_litter_above_0*epa.f_sur_met_lit,
                cpa.C_litter_above_0*(1-epa.f_sur_met_lit),
                cpa.C_litter_below_0*(1-epa.f_root_met_lit),
                cpa.C_litter_below_0*epa.f_root_met_lit,
                epa.C_sur_mic_0,
                epa.C_soil_mic_0,
                cpa.C_slow_som_0,
                cpa.C_pass_som_0
            ]
        ).reshape([11, 1])   # Initial carbon pool size
        
        # initialize carbon pools 
        X=x_init   
        
        # initialize first respiration value 
        co2_rh=cpa.rh_0
        f_veg_lit=cpa.f_veg_lit_0
        #f_lit_soil=cpa.f_lit_soil_0
        #f_lit_soil=f_veg_lit
        # fixme:
        # slight change to the original
        # I would like to start the solution with the initial values
        # m=0 means after 0 months = in the initial step
        #B=A@K
        #pa=Parameters.from_EstimatedParametersAndUnEstimatedParameters(epa,cpa)
        #B=make_compartmental_matrix_func(pa)(0,X)
        def Rh_calc (TS, M, T0, E, KM):
            TS = TS - 273.15
            if TS > T0:
                rh_out = np.exp(E * (1 / (10 - T0) - 1 / (TS - T0))) * M / (KM + M)
            else:
                rh_out = 0
            return rh_out

        for m in range(0, cpa.number_of_months):
            x_fin[m, :] = X.reshape(1, 11)
            npp_in = cpa.npp[m] 
            rh_fin[m, 0] = co2_rh
            f_veg_lit_fin[m, 0] = f_veg_lit
            #f_lit_som_fin[m, 0] = f_lit_soil
            co2_rh = 0; f_veg_lit = 0; f_lit_soil = 0
            rh_modifier = Rh_calc(cpa.tsl[m], cpa.mrso[m], epa.T_0, epa.E, epa.KM)
            ksi = np.array(
                [
                    1,
                    1,
                    1,
                    rh_modifier,
                    rh_modifier,
                    rh_modifier,
                    rh_modifier,
                    rh_modifier,
                    rh_modifier,
                    rh_modifier,
                    rh_modifier
                ]
            ).reshape([11, 1])  # environmental modifiers
            for d in range(0, days[m % 12]):
                K_new = K*ksi
                X = X + b*npp_in + A@K_new@X
                co2_rate = [0, 0, 0,
                        (1-f84)*K[3, 3]*ksi[3],
                        (1-f85-f105)*K[4, 4]*ksi[4],
                        (1-f106-f96)*K[5, 5]*ksi[5],
                        (1-f97)*K[6, 6]*ksi[6],
                        (1-f108)*K[7, 7]*ksi[7],
                        (1-f109-f119)*K[8, 8]*ksi[8],
                        (1-f910-f1110)*K[9, 9]*ksi[9],
                        (1-f911)*K[10, 10]*ksi[10]
                    ]
                co2 = np.sum(co2_rate*X.reshape(1, 11))
                co2_rh = co2_rh + co2/days[m % 12]   # monthly average rh
                #LiangJY note: May caluclate the co2 flux before updating X
                #              but have not modified yet
                '''
                litterfall_rate = [f41*K[0, 0]*ksi[0], f52*K[1, 1]*ksi[1], f63*K[2, 2]*ksi[2], 0, 0, 0, 0, 0, 0]
                litterfall = np.sum(litterfall_rate * X.reshape(1, 11))
                f_veg_lit = f_veg_lit + litterfall / days[m % 12]  # monthly average flux from veg to litter
                litter_to_soil_rate = [
                        0, 0, 0, f74*K[3, 3]*ksi[3]+f84*K[3, 3]*ksi[3]+f84*K[3, 3]*ksi[3],
                        f75*K[4, 4]*ksi[4] + f85*K[4, 4]*ksi[4] + f95*K[4, 4]*ksi[4],
                        f76*K[5, 5]*ksi[5] + f86*K[5, 5]*ksi[5] + f96*K[5, 5]*ksi[5],
                        0, 0, 0
                    ]
                litter_to_soil = np.sum(litter_to_soil_rate * X.reshape(1, 11))
                f_lit_soil = f_lit_soil + litter_to_soil / days[m % 12] # monthly average flux from litter to soil
                '''
        # We create an output that has the same shape
        # as the obvervations to make the costfunctions 
        # easier. 
        # To this end we project our 10 output variables of the matrix simulation
        # onto the 6 data streams by summing up the 3 litter pools into one
        # and also the 3 soil pools into one
        #C_litter_above = x_fin[:,3] + x_fin[:,4]
        C_litter_above = np.sum(x_fin[:, 4:5], axis=1).reshape(cpa.number_of_months,1)
        C_litter_below = np.sum(x_fin[:, 6:7], axis=1).reshape(cpa.number_of_months,1)
        #C_litter_below = x_fin[:,5]
        #c_litter = np.sum(x_fin[:,3:6],axis=1).reshape(cpa.number_of_months,1)
        #c_soil = np.sum(x_fin[:,6:9],axis=1).reshape(cpa.number_of_months,1)
        #from IPython import embed; embed()
        out_simu = np.concatenate(
            [
                x_fin[:, 0:3],  # the first 3 pools are used as they are
                C_litter_above,
                C_litter_below,
                x_fin[:, 9:11],
                rh_fin,
                f_veg_lit_fin,
                #f_lit_som_fin
            ]
            , axis=1
        )
        return out_simu

    return param2res

################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################

# # alternative implementation and helper functions. If you do not want to use it # comment it.
# def make_param2res_2(
#         cpa: UnEstimatedParameters
#     ) -> Callable[[np.ndarray], np.ndarray]:
#     # This function is an alternative implementation with the same results as
#     # make_param2res
#     # Internally it uses a slightly higher level of abstraction and devides the task
#     # into more numerous but smaller testable and reusable units.
#     # Although both properties are not necessary to replicate the original
#     # code they provide a different perspective which is easier to reuse the code
#     # in  a wider range of models e.g. models with daily driver data, time
#     # dependent or even nonlinear matrices and so on.
#     # Thus it allows to test small parts of the code against the respective parts of the
#     # symbolic framework
#     #
#     # It differs in the following respects:
#     # 0.)   We use named tuples for the parameters (just for readability)
#     # 1.)   We use a seperate function to costruct the matrix which will be
#     #       a function B(i,X)  of the iteration it  and the present poolvalues X
#     #       (althouhg in this case unnecessary since B is constant but
#     #       the dependence on 'i' becomes useful if you want to include
#     #       an environmental scalar and the dependence on X makes it possible
#     #       to include nonlinearities.
#     # 2.)   We build a daily advancing model that can provide output for an arbitrary
#     #       selection of days.  To do so we provide all driver data as
#     #       functions of the smalles timestep (here day with index i), which in
#     #       the case of this model means that we provide the same npp value for
#     #       all the days in a given month.
#     # 3.)   We translate the index of a given month to the appropriate day index
#     #       and apply the dayly model of 2.). Again this seems cumbersome for this
#     #       example but allows us to reuse the daily model for all applications.
#     #       This is espacially usefull for testing since we only need some dayly timesteps.
#     #       It makes it also easier to keep an overview over the appropriate
#     #       units: If the smallest timestep is a day, then all time related parameters
#     #       have to be provided in the corresponding  units, regardless of the
#     #       number of available datapoints
#     #
#     def param2res(pa):
#         epa=EstimatedParameters(*pa)
#         # here we want to store only monthly values
#         # although the computation takes place on a daily basis
#         V_init = construct_V0(cpa,epa)
#         # compute the days when we need the results
#         # to be able to compare to the monthly output
#         day_indices = month_2_day_index(range(cpa.number_of_months))
#         print("day_indices=",day_indices)
#         apa = Parameters.from_EstimatedParametersAndUnEstimatedParameters(epa,cpa)
#
#         mpa = ModelParameters(
#             **{
#                 k:v for k,v in apa._asdict().items()
#                 if k in ModelParameters._fields
#             }
#         )
#         full_res = run_forward_simulation(
#             V_init=V_init,
#             day_indices=day_indices,
#             mpa=mpa
#         )
#
#         # project the litter and soil pools
#         tot_len=cpa.number_of_months
#         c_litter = np.sum(full_res[:,3:6],axis=1).reshape(tot_len,1)
#         c_soil = np.sum(full_res[:,6:9],axis=1).reshape(tot_len,1)
#         out_simu = np.concatenate(
#             [
#                 full_res[:,0:3], # the first 3 pools are used as they are
#                 c_litter,
#                 c_soil,
#                 full_res[:,9:10]
#             ]
#             ,axis=1
#         )
#         return out_simu
#
#     return param2res
#

def run_forward_simulation(
        V_init,
        day_indices,
        mpa
    ):
        tsi = make_daily_iterator(
            V_init,
            mpa=mpa
        )

        def g(acc, i):
            xs,co2s,acc_co2,acc_days = acc
            v = tsi.__next__()
            d_pools = v[0:-1,:]
            d_co2=v[-1:,:]
            acc_co2 += d_co2
            acc_days += 1
            if i in day_indices:
                xs += [d_pools] 
                co2s +=[acc_co2/acc_days]
                acc_co2=np.array([0.0]).reshape(1,1)
                acc_days = 0
                
            acc = (xs,co2s,acc_co2,acc_days)
            return acc
        xs,co2s,acc_days,_ =  reduce(g,range(max(day_indices)+1),([],[],0,0))
                
        def h(tup):
            x, co2 = tup
            return np.transpose(np.concatenate([x,co2]))
    
        values_with_accumulated_co2 = [v for v in  map(h,zip(xs,co2s))]
        RES = np.concatenate(values_with_accumulated_co2 , axis=0)  
        return RES

def make_daily_iterator(
        V_init,
        mpa
    ):
         
        # Construct npp(day)
        # in general this function can depend on the day i and the state_vector X
        # e.g. typically the size fo X.leaf...
        # In this case it only depends on the day i 
        def npp_func(day,X):
            return mpa.npp[day_2_month_index(day)] 

        # b (b vector for partial allocation) 
        beta_wood = 1- mpa.beta_leaf- mpa.beta_root
        b = np.array(
            [
                mpa.beta_leaf,
                mpa.beta_root,
                beta_wood,
                0,
                0,
                0,
                0,
                0,
                0
            ],
        ).reshape(9,1)
        # Now construct B matrix B=A*K 
        B_func  = make_compartmental_matrix_func(
            mpa=mpa,
        )
        # Build the iterator which is the representation of a dynamical system
        # for looping forward over the results of a difference equation
        # X_{i+1}=f(X_{i},i)
        # This is the discrete counterpart to the initial value problem 
        # of the continuous ODE  
        # dX/dt = f(X,t) and initial values X(t=0)=X_0
        
        def f(it,V):
            X = V[0:9]
            co2 = V[9]
            npp  = npp_func(it,X)
            B = B_func(it,X)
            X_new = X + npp * b + B@X

            # we also compute the respired co2 in every (daily) timestep
            # and use this part of the solution later to sum up the monthly amount
            co2_new =  respiration_from_compartmental_matrix(B,X) 
            
            V_new = np.concatenate((X_new,np.array([co2_new]).reshape(1,1)), axis=0)
            return V_new
    
    
        #X_0 = np.array(x_init).reshape(9,1) #transform the tuple to a matrix
        #co2_0 = np.array([0]).reshape(1,1)
        #V_0 = np.concatenate((X_0, co2_0), axis=0)

        return TimeStepIterator2(
                initial_values=V_init,
                f=f,
                #max_it=max(day_indices)+1
        )
        

def make_compartmental_matrix_func(
        mpa
    ):
    # Now construct A matrix
    # diagonal 
    # make sure to use 1.0 instead of 1 otherwise it will be an interger array
    # and round your values....
    A =np.diag([-1.0 for i in range(9)]) 
    # because of python indices starting at 0 we have A[i-1,j-1]=fij
    #
    #A = np.array([  -1,   0,   0,   0,   0,   0,   0,   0,   0,
    #                 0,  -1,   0,   0,   0,   0,   0,   0,   0,
    #                 0,   0,  -1,   0,   0,   0,   0,   0,   0,
    #               f41, f42,   0,  -1,   0,   0,   0,   0,   0,
    #               f51, f52,   0,   0,  -1,   0,   0,   0,   0,
    #                 0,   0, f63,   0,   0,  -1,   0,   0,   0,
    #                 0,   0,   0, f74, f75,   0,  -1,   0,   0,
    #                 0,   0,   0,   0, f85, f86, f87,  -1,   0,
    #                 0,   0,   0,   0,   0, f96, f97, f98,  -1 ]).reshape([9,9])   # tranfer

    # note that the matrix description of a model is implicitly related to the
    # order of pools in the state_vector and not independent from it.

    A[3,0] = mpa.f_leaf2metlit
    A[3,1] = mpa.f_root2metlit
    A[4,0] = 1.0 - mpa.f_leaf2metlit
    A[4,1] = 1.0 - mpa.f_root2metlit
    A[5,2] = mpa.f_wood2CWD 
    A[6,3] = mpa.f_metlit2mic 
    A[6,4] = mpa.f_metlit2mic * (1 - mpa.lig_leaf)
    A[7,4] = 0.7 * mpa.lig_leaf
    A[7,5] = 0.4 * (1 - mpa.lig_wood)
    A[8,5] = 0.7 * mpa.lig_wood
    A[7,6] = (0.85 - 0.68 * (mpa.clay+mpa.silt)) * (0.997 - 0.032 * mpa.clay)
    A[8,6] = (0.85 - 0.68 * (mpa.clay+mpa.silt)) * (0.003 + 0.032 * mpa.clay)
    A[8,7] = 0.45 * (0.003 + 0.009 * mpa.clay)

    #turnover rate per day of pools: 
    K = np.diag([
        mpa.k_leaf,
        mpa.k_root,
        mpa.k_wood,
        mpa.k_metlit,
        mpa.k_metlit/(5.75*np.exp(-3*mpa.lig_leaf)),
        mpa.k_metlit/20.6,
        mpa.k_mic,
        mpa.k_slowsom,
        mpa.k_passsom
    ])
    # in the general nonautonomous nonlinear case
    # B will depend on an it,X (althouh in this case it does not depend on either
    def B_func(it,X): 
        return A@K

    return B_func
#
# def construct_V0(
#         cpa :UnEstimatedParameters,
#         epa :EstimatedParameters
#     ) -> np.ndarray:
#     """Construct the initial values for the forward simulation
#     from constant and eveluated parameters
#
#     param: cpa : constant parameeters
#     param: epa : estimated parameters
#     """
#     # to make sure that we are in the right order we use the
#     # StateVariables namedtuple
#     X_0 = StateVariables(
#         C_leaf=cpa.C_leaf_0,
#         C_root=cpa.C_root_0,
#         C_wood=cpa.C_wood_0,
#         C_metlit=epa.C_metlit_0,
#         C_strlit=epa.C_strlit_0,
#         C_cwd=C_cwd_0,
#         C_mic=epa.C_mic_0,
#         C_slowsom=cpa.csoil_0- epa.C_mic_0 - epa.C_passom_0,
#         C_passsom=epa.C_passom_0
#     )
#     # add the respiration start value to the tuple
#     V_0 = (*X_0,cpa.rh_0)
#     return np.array(V_0).reshape(10,1)
