#!/usr/bin/env python
# coding=utf-8

import casadi as ca
import numpy as np

from draw import Draw_MPC_tracking

def shift_movement(T, t0, x0, u, x_n, f):
    f_value = f(x0, u[0])
    st = x0 + T*f_value
    t = t0 + T
    u_end = np.concatenate((u[1:], u[-1:]))
    x_n = np.concatenate((x_n[1:], x_n[-1:]))
    return t, st, u_end, x_n

def desired_trajectory(t, x0_, N_):
    pass

def prediction_state(x0, u, T, N):
    # define predition horizon function
    states = np.zeros((N+1, 3))
    states[0, :] = x0
    for i in range(N):
        states[i+1, 0] = states[i, 0] + u[i, 0] * np.cos(states[i, 2]) * T
        states[i+1, 1] = states[i, 1] + u[i, 0] * np.sin(states[i, 2]) * T
        states[i+1, 2] = states[i, 2] + u[i, 1] * T
    return states

if __name__ == '__main__':
    T = 0.5
    N = 8
    rob_diam = 0.3 # [m]
    v_max = 0.6
    omega_max = np.pi/4.0

    opti = ca.Opti()
    # control variables, linear velocity v and angle velocity omega
    opt_controls = opti.variable(N, 2)
    v = opt_controls[:, 0]
    omega = opt_controls[:, 1]
    opt_states = opti.variable(N+1, 3)
    x = opt_states[:, 0]
    y = opt_states[:, 1]
    theta = opt_states[:, 2]

    # parameters, these parameters are the reference trajectories of the pose and inputs
    opt_u_ref = opti.parameter(N, 2)
    opt_x_ref = opti.parameter(N+1, 3)
    # create model
    f = lambda x_, u_: ca.vertcat(*[u_[0]*np.cos(x_[2]), u_[0]*np.sin(x_[2]), u_[1]])
    f_np = lambda x_, u_: np.array([u_[0]*np.cos(x_[2]), u_[0]*np.sin(x_[2]), u_[1]])

    ## init_condition
    opti.subject_to(opt_states[0, :] == opt_x_ref[0, :])
    for i in range(N):
        x_next = opt_states[i, :] + f(opt_states[i, :], opt_controls[i, :]).T*T
        opti.subject_to(opt_states[i+1, :]==x_next)
    
    ## define the cost function
    ### some addition parameters
    Q = np.array([[1.0, 0.0, 0.0],[0.0, 1.0, 0.0],[0.0, 0.0, .5]])
    R = np.array([[0.5, 0.0], [0.0, 0.05]])
    #### cost function
    obj = 0 #### cost
    for i in range(N):
        state_error_ = opt_states[i, :] - opt_x_ref[i, :]
        control_error_ = opt_controls[i, :] - opt_u_ref[i, :]
        obj = obj + ca.mtimes([state_error_.T, Q, state_error_]) + ca.mtimes([control_error_.T, R, control_error_])

    opti.minimize(obj)

    #### boundrary and control conditions
    opti.subject_to(opti.bounded(-2.0, x, 2.0))
    opti.subject_to(opti.bounded(-2.0, y, 2.0))
    opti.subject_to(opti.bounded(-np.pi, theta, np.pi))
    opti.subject_to(opti.bounded(-v_max, v, v_max))
    opti.subject_to(opti.bounded(-omega_max, omega, omega_max))

    opts_setting = {'ipopt.max_iter':2000, 'ipopt.print_level':0, 'print_time':0, 'ipopt.acceptable_tol':1e-8, 'ipopt.acceptable_obj_change_tol':1e-6}

    opti.solver('ipopt', opts_setting)
    final_state = np.array([1.5, 1.5, 0.0])
    opti.set_value(opt_xs, final_state)

    t0 = 0
    init_state = np.array([0.0, 0.0, 0.0])
    u0 = np.zeros((N, 2))
    next_trajectories = np.tile(init_state, N+1).reshape(N+1, -1)
    next_controls = np.zeros((N, 2))
    next_states = np.zeros((N+1, 3))
    x_c = [] # contains for the history of the state
    u_c = []
    t_c = [t0] # for the time
    xx = []
    sim_time = 20.0

    ## start MPC
    mpciter = 0

    while(np.linalg.norm(current_state-final_state)>1e-2 and mpciter-sim_time/T<0.0):
        ## set parameter, here only update initial state of x (x0)
        opti.set_value(opt_x0, current_state)
        opti.set_initial(opt_controls, u0.reshape(N, 2))# (N, 2)
        opti.set_initial(opt_states, next_states) # (N+1, 3)
        ## solve the problem once again
        sol = opti.solve()
        ## obtain the control input
        u_res = sol.value(opt_controls)
        x_m = sol.value(opt_states)
        print(u_res[:3])
        print(x_m[:3])
        u_c.append(u_res[0, :])
        t_c.append(t0)
        x_c.append(x_m)
        t0, current_state_, u0, next_states = shift_movement(T, t0, current_state, u_res, x_m, f_np)
        current_state = current_state_.copy()
        mpciter = mpciter + 1
        xx.append(current_state)

    ## after loop
    print(mpciter)
    print('final error {}'.format(np.linalg.norm(final_state-current_state)))
    ## draw function
    draw_result = Draw_MPC_Obstacle(rob_diam=0.3, init_state=init_state, target_state=final_state, robot_states=xx, obstacle=np.array([obs_x, obs_y, obs_diam/2.]), export_fig=False)
