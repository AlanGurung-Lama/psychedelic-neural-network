import sys
import torch
import matplotlib.pyplot as plt
from scipy.fftpack import rfftfreq
sys.path.insert(0,r'\\rds.imperial.ac.uk\rds\user\ag1523\home\fyp-main\pytorch_models')
import Stimulus_PDCM_BOLD as spb
import numpy as np
import math
from scipy.signal import lfilter

sys.path.insert(1,r'\\rds.imperial.ac.uk\rds\user\ag1523\home\fyp-main\pytorch_models\noise_gen')
#from NoiseTimeSeries import generate_pink_noise
#from RevisedNoiseTimeSeries import generate_pink_noise2
#from Filter import apply_white_to_pink_filter
#from KellettMethod import recursive_pink_noise
#from White_Pink_Filter import design_lowpass_filter
from Pink_Noise_Java import generate_pink_noise




device = 'cuda' if torch.cuda.is_available() else 'cpu'

indicator = True  # True for CBF-CBV coupling, False for uncoupling
plot_all = True  # plot all variables together

# Reproduce Fig. 3
stimulus = 1  # stimulus duration (unit: sec)
func = spb.StimulusPDCMBOLD(w=stimulus, mu=1, lamb=0.2,
                            c=1)  # solid thick line - TMTT would need to go in here - move to getEulerBOLD


def euler_1st(func, t, h, var_init, indicator,  alpha, beta, select=False, add_noise=False):
    """Run the first-order forward Euler method and return the final list of y
       (BOLD)

    Arg:
    - func -- spb.StimulusPDCMBOLD(), with specified input parameters
    - t -- list of t values for iteration and plot
    - var_init -- initial values of all variables
    - indicator -- boolean variable controlling using CBF-CBV coupling model or
                   not
    - select -- boolean variable controlling whether appending selected values
                to the output t and y lists only

    Return:
    - Lists of values of the all the variables from both the ODEs and the
      algebaric equations after running the Runge-Kutta method
    - List of stimulus values
    """
    # Initial values
    (xE_val, xI_val, a_val, f_val, v_val, q_val, fout_val, E_val, y_val
     ) = var_init
    # List for plotting
    t_list = [t[0]]  # Output list if select=True
    u_list = []
    xE_list = [xE_val]
    xI_list = [xI_val]
    a_list = [a_val]
    f_list = [f_val]
    v_list = [v_val]
    q_list = [q_val]
    E_list = [E_val]
    fout_list = [fout_val]
    y_list = [torch.tensor(y_val, requires_grad=True).to(device)]
    if add_noise:
        # noise, _ = generate_pink_noise(len(t), t[-1], alpha, beta) 
        # noise = torch.from_numpy(generate_pink_noise2(len(t), alpha, beta, 'randpower'))
        
        noise = generate_pink_noise(beta=beta, alpha=alpha, n_samples=len(t))
    for i in range(0, len(t)-1):
        # Stimulus
        u_val = func.sti_u(t[i])

        # ODEs
        xE_val_next = xE_val + h*func.ode_xE(u=u_val, xE=xE_val, xI=xI_val) + (math.sqrt(h) * noise[i] if add_noise else 0)
        xI_val_next = xI_val + h*func.ode_xI(xE=xE_val, xI=xI_val)
        a_val_next = a_val + h*func.ode_a(a=a_val, xE=xE_val)
        f_val_next = f_val + h*func.ode_f(a=a_val, f=f_val)
        v_val_next = v_val + h*func.ode_v(f=f_val, fout=fout_val)
        q_val_next = q_val + h*func.ode_q(f=f_val, E=E_val, fout=fout_val,
                                          q=q_val, v=v_val)
        # Non-ODEs
        if indicator is True:
            fout_val_next = func.equ_fout(v=v_val_next, couple=True)
        else:
            fout_val_next = func.equ_fout(v=v_val_next, f=f_val_next,
                                          couple=False)
        E_val_next = func.equ_E(f=f_val_next)
        y_val_next = func.equ_y(q=q_val_next, v=v_val_next)
        if not torch.is_tensor(y_val_next):
            y_val_next = torch.tensor(y_val_next, requires_grad=True).to(device)
        # Append results
        if select is False:
            u_list.append(u_val)
            xE_list.append(xE_val_next)
            xI_list.append(xI_val_next)
            a_list.append(a_val_next)
            f_list.append(f_val_next)
            v_list.append(v_val_next)
            q_list.append(q_val_next)
            fout_list.append(fout_val_next)
            E_list.append(E_val_next)
            y_list.append(y_val_next)
        else:
            if h > 0.01:
                t_list.append(t[i+1])
                y_list.append(y_val_next)
            elif i % 10 == 0:  # append every 10 values
                t_list.append(t[i+1])
                y_list.append(y_val_next.to(device))

        # Overwrite the next value to the current value for next iteration
        xE_val = xE_val_next
        xI_val = xI_val_next
        a_val = a_val_next
        f_val = f_val_next
        v_val = v_val_next
        q_val = q_val_next
        fout_val = fout_val_next
        E_val = E_val_next

    u_list.append(func.sti_u(t[-1]))
    if select is False:
        u_list = torch.tensor(u_list)
        xE_list = torch.tensor(xE_list)
        xI_list = torch.tensor(xI_list)
        a_list = torch.tensor(a_list)
        f_list = torch.tensor(f_list)
        v_list = torch.tensor(v_list)
        q_list = torch.tensor(q_list)
        fout_list = torch.tensor(fout_list)
        E_list = torch.tensor(E_list)
        return (u_list, xE_list, xI_list, a_list, f_list, v_list, q_list,
                fout_list, E_list, y_list)
    else:
        return t_list, y_list

def getEulerBOLD(alpha=1.0, beta=1.0, noise=False, length=None, **kwargs):

    func.setParams(**kwargs)
    t_ref = spb.time_ref(stimulus)  # controls initial and final t
    h = 0.01  # step size, unit: sec
    if length == None:
        t = torch.arange(t_ref[0], t_ref[-1] + t_ref[1], h)  # all t values
    else:
        t = torch.arange(t_ref[0], length + t_ref[1], h)

    # Initial conditions
    var_init = [spb.xE_init, spb.xI_init, spb.a_init, spb.f_init, spb.v_init,
                spb.q_init, spb.fout_init, spb.E_init, spb.y_init]

    # Results
    (u_list, xE_list, xI_list, a_list, f_list, v_list, q_list, fout_list,
     E_list, y_list) = euler_1st(func, t, h, var_init, indicator, alpha, beta, False, noise)

    # Return the tensors you want to compute gradients with respect to
    return t, y_list

def getEulerFandV(alpha=1.0, beta=1.0, noise=False, length=None, **kwargs):

    func.setParams(**kwargs)
    t_ref = spb.time_ref(stimulus)  # controls initial and final t
    h = 0.01  # step size, unit: sec
    if length == None:
        t = torch.arange(t_ref[0], t_ref[-1] + t_ref[1], h)  # all t values
    else:
        t = torch.arange(t_ref[0], length + t_ref[1], h)

    # Initial conditions
    var_init = [spb.xE_init, spb.xI_init, spb.a_init, spb.f_init, spb.v_init,
                spb.q_init, spb.fout_init, spb.E_init, spb.y_init]

    # Results
    (u_list, xE_list, xI_list, a_list, f_list, v_list, q_list, fout_list,
     E_list, y_list) = euler_1st(func, t, h, var_init, indicator, alpha, beta, False, noise)

    # Return the tensors you want to compute gradients with respect to
    return t, f_list, v_list