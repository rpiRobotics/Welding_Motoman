from copy import deepcopy
from pathlib import Path
import pickle
import sys
sys.path.append('../scan/scan_tools/')
sys.path.append('../scan/scan_plan/')
sys.path.append('../scan/scan_process/')
from robotics_utils import *
from motoman_def import *
from scan_utils import *
from scanProcess import *
from weld_dh2v import *

from weld_dh2v import *
from general_robotics_toolbox import *
from RobotRaconteur.Client import *
import matplotlib.pyplot as plt
import time
import datetime
import numpy as np
import open3d as o3d

def robot_weld_path_gen(all_layer_z,forward_flag,base_layer):
    R=np.array([[-0.7071, 0.7071, -0.    ],
            [ 0.7071, 0.7071,  0.    ],
            [0.,      0.,     -1.    ]])
    x0 =  1684	# Origin x coordinate
    y0 = -1179 + 428	# Origin y coordinate
    z0 = -260   # 10 mm distance to base

    weld_p=[]
    if base_layer: # base layer
        weld_p.append([x0 - 33, y0 - 20, z0+10])
        weld_p.append([x0 - 33, y0 - 20, z0])
        weld_p.append([x0 - 33, y0 - 105 , z0])
        weld_p.append([x0 - 33, y0 - 105 , z0+10])
    else: # top layer
        weld_p.append([x0 - 33, y0 - 30, z0+10])
        weld_p.append([x0 - 33, y0 - 30, z0])
        weld_p.append([x0 - 33, y0 - 95 , z0])
        weld_p.append([x0 - 33, y0 - 95 , z0+10])

    if not forward_flag:
        weld_p = weld_p[::-1]

    all_path_T=[]
    for layer_z in all_layer_z:
        path_T=[]
        for p in weld_p:
            path_T.append(Transform(R,p+np.array([0,0,layer_z])))

        all_path_T.append(path_T)
    
    return all_path_T

zero_config=np.zeros(6)
# 0. robots. Note use "(robot)_pose_mocapcalib.csv"
config_dir='../config/'
robot_weld=robot_obj('MA2010_A0',def_path=config_dir+'MA2010_A0_robot_default_config.yml',d=15,tool_file_path=config_dir+'torch.csv',\
	pulse2deg_file_path=config_dir+'MA2010_A0_pulse2deg_real.csv',\
    base_marker_config_file=config_dir+'MA2010_marker_config/MA2010_marker_config.yaml',tool_marker_config_file=config_dir+'weldgun_marker_config/weldgun_marker_config.yaml')
robot_scan=robot_obj('MA1440_A0',def_path=config_dir+'MA1440_A0_robot_default_config.yml',tool_file_path=config_dir+'mti.csv',\
	base_transformation_file=config_dir+'MA1440_pose.csv',pulse2deg_file_path=config_dir+'MA1440_A0_pulse2deg_real.csv',\
    base_marker_config_file=config_dir+'MA1440_marker_config/MA1440_marker_config.yaml')
positioner=positioner_obj('D500B',def_path=config_dir+'D500B_robot_default_config.yml',tool_file_path=config_dir+'positioner_tcp.csv',\
    base_transformation_file=config_dir+'D500B_pose.csv',pulse2deg_file_path=config_dir+'D500B_pulse2deg_real.csv',\
    base_marker_config_file=config_dir+'D500B_marker_config/D500B_marker_config.yaml',tool_marker_config_file=config_dir+'positioner_tcp_marker_config/positioner_tcp_marker_config.yaml')

Table_home_T = positioner.fwd(np.radians([-15,180]))
T_S1TCP_R1Base = np.linalg.inv(np.matmul(positioner.base_H,H_from_RT(Table_home_T.R,Table_home_T.p)))
T_R1Base_S1TCP = np.linalg.inv(T_S1TCP_R1Base)

#### change base H to calibrated ones ####
robot_scan.base_H = H_from_RT(robot_scan.T_base_basemarker.R,robot_scan.T_base_basemarker.p)
positioner.base_H = H_from_RT(positioner.T_base_basemarker.R,positioner.T_base_basemarker.p)
T_to_base = Transform(np.eye(3),[0,0,-380])
positioner.base_H = np.matmul(positioner.base_H,H_from_RT(T_to_base.R,T_to_base.p))

path_R=np.array([[-0.7071, 0.7071, -0.    ],
            [ 0.7071, 0.7071,  0.    ],
            [0.,      0.,     -1.    ]])
R_S1TCP = np.matmul(T_S1TCP_R1Base[:3,:3],path_R)

build_height_profile=False
plot_correction=False
plot_pcd = False
show_layer = []
# show_layer = [12]

x_lower = -99999
x_upper = 999999

# start_id=0
# end_id=-1

start_id=75
end_id=-75

datasets=['baseline','correction']

datasets_h_mean={}
datasets_h_std={}
for dataset in datasets:

    if dataset=='baseline':
        data_dir = '../data/wall_weld_test/moveL_100_baseline_weld_scan_2023_07_07_15_20_56/'
    elif dataset=='correction':
        # data_dir = '../data/wall_weld_test/moveL_160_noconstraints_weld_scan_2023_07_05_18_59_53/'
        data_dir = '../data/wall_weld_test/moveL_100_weld_scan_2023_07_24_11_19_58/'
        # data_dir = '../data/wall_weld_test/moveL_100_weld_scan_2023_08_02_15_17_25/'
    elif dataset=='repeat 1':
        data_dir = '../data/wall_weld_test/moveL_100_repeat_weld_scan_2023_08_02_16_03_50/'
    elif dataset=='repeat 2':
        data_dir = '../data/wall_weld_test/moveL_100_repeat_weld_scan_2023_08_02_17_07_02/'

    forward_flag=False
    all_profile_height=[]
    all_correction_layer=[]
    all_h_mean=[]
    all_h_std=[]
    pcd_wall = None
    for i in range(0,9999999):
        try:
            weld_dir=data_dir+'layer_'+str(i)+'/'
            weld_q=np.loadtxt(weld_dir+'weld_js_exe.csv',delimiter=',')
            weld_stamp=np.loadtxt(weld_dir+'weld_robot_stamps.csv',delimiter=',')
            scan_dir=weld_dir+'scans/'
            pcd = o3d.io.read_point_cloud(scan_dir+'processed_pcd.pcd')
            profile_height = np.load(scan_dir+'height_profile.npy')
            q_out_exe=np.loadtxt(scan_dir+'scan_js_exe.csv',delimiter=',')
            robot_stamps=np.loadtxt(scan_dir+'scan_robot_stamps.csv',delimiter=',')
            with open(scan_dir+'mti_scans.pickle', 'rb') as file:
                mti_recording=pickle.load(file)

            print("Layer",i)
            print("Forward:",not forward_flag)

            if pcd_wall is None:
                pcd_wall = deepcopy(pcd)
            else:
                pcd_wall = pcd_wall + pcd
            
            if plot_pcd:
                visualize_pcd([pcd])
        except:
            break

        if build_height_profile and (i in show_layer):
            curve_x_start=43
            curve_x_end=-41
            crop_extend=10
            z_height_start=20
            scan_process = ScanProcess(robot_scan,positioner)
            crop_min=(curve_x_end-crop_extend,-30,-10)
            crop_max=(curve_x_start+crop_extend,30,z_height_start+30)
            crop_h_min=(curve_x_end-crop_extend,-20,-10)
            crop_h_max=(curve_x_start+crop_extend,20,z_height_start+30)
            q_init_table=np.radians([-15,200])
            pcd = scan_process.pcd_register_mti(mti_recording,q_out_exe,robot_stamps,static_positioner_q=q_init_table)
            # visualize_pcd([pcd])
            pcd = scan_process.pcd_noise_remove(pcd,nb_neighbors=40,std_ratio=1.5,\
                                                min_bound=crop_min,max_bound=crop_max,cluster_based_outlier_remove=True,cluster_neighbor=1,min_points=100)
            visualize_pcd([pcd])
            profile_height = scan_process.pcd2height(deepcopy(pcd),-1)
            profile_height = np.array(profile_height)

        all_profile_height.append(profile_height)

        h_std_thres=0.48
        # h_std_thres=0
        h_std = np.std(profile_height[:,1])
        if i>2 and h_std>h_std_thres and dataset != "baseline":
            all_correction_layer.append(i)

        if (plot_correction and (i in show_layer)):
            # weld path
            if forward_flag:
                curve_sliced_relative=[np.array([ 3.30445152e+01,  1.72700000e+00,  3.31751393e+01,  1.55554573e-04,
       -6.31394918e-20, -9.99881509e-01]), np.array([-3.19477829e+01,  1.72700000e+00,  3.31751393e+01,  1.55554573e-04,
       -6.31394918e-20, -9.99881509e-01])]
            else:
                curve_sliced_relative=[np.array([-3.19477829e+01,  1.72700000e+00,  3.31751393e+01,  1.55554573e-04,
       -6.31394918e-20, -9.99881509e-01]), np.array([ 3.30445152e+01,  1.72700000e+00,  3.31751393e+01,  1.55554573e-04,
       -6.31394918e-20, -9.99881509e-01])]

            ## parameters
            noise_h_thres = 3
            min_v=-1
            max_v=9999
            h_std_thres=h_std_thres
            nominal_v=5
            input_dh=v2dh_loglog(nominal_v,100)
            num_l=40
            ############

            ### delete noise
            mean_h = np.mean(profile_height[:,1])
            profile_height=np.delete(profile_height,np.where(profile_height[:,1]-mean_h>noise_h_thres),axis=0)
            profile_height=np.delete(profile_height,np.where(profile_height[:,1]-mean_h<-noise_h_thres),axis=0)
            ###
            mean_h = np.mean(profile_height[:,1])
            h_largest = np.max(profile_height[:,1])
            # 3. h_target = mean_h + designated dh value
            h_target = mean_h+input_dh

            h_std = np.std(profile_height[:,1])
            print("H STD:",h_std)
            if h_std<=h_std_thres:
                print("H std smaller than threshold.")
                
                nominal_dh = v2dh_loglog(nominal_v,mode=160)
                print("Change target dh to:",nominal_dh)
                h_target = mean_h+nominal_dh
                
                curve_sliced_relative_correct = []
                path_T_S1 = []
                this_weld_v = []
                all_dh=[]
                for curve_i in range(len(curve_sliced_relative)):
                    this_p = np.array([curve_sliced_relative[curve_i][0],curve_sliced_relative[curve_i][1],h_target])
                    curve_sliced_relative_correct.append(np.append(this_p,curve_sliced_relative[curve_i][3:]))
                    path_T_S1.append(Transform(R_S1TCP,curve_sliced_relative_correct[-1][:3]))
                    this_weld_v.append(nominal_v)
                    all_dh.append(nominal_dh)
                this_weld_v.pop()
                all_dh.pop()

                # plt.scatter(profile_height[:,0],profile_height[:,1]-np.mean(profile_height[:,1]))
                # plt.show()

                all_profile=[profile_height]

            else:
                # chop curve
                curve_sliced_relative_chop = np.linspace(curve_sliced_relative[0],curve_sliced_relative[-1],num_l+1)

                # find v  
                # new curve in positioner frame
                curve_sliced_relative_correct = []
                this_p = np.array([curve_sliced_relative_chop[0][0],curve_sliced_relative_chop[0][1],h_target])
                curve_sliced_relative_correct.append(np.append(this_p,curve_sliced_relative_chop[0][3:]))
                path_T_S1 = [Transform(R_S1TCP,curve_sliced_relative_correct[-1][:3])]
                this_weld_v = []
                seg_mean_h = []
                all_dh= []
                all_profile=[]
                for l in range(1,num_l+1):
                    # path
                    this_p = np.array([curve_sliced_relative_chop[l][0],curve_sliced_relative_chop[l][1],h_target])
                    curve_sliced_relative_correct.append(np.append(this_p,curve_sliced_relative_chop[l][3:]))
                    path_T_S1.append(Transform(R_S1TCP,curve_sliced_relative_correct[-1][:3]))

                    # velocity
                    min_x = min(curve_sliced_relative_chop[l-1][0],curve_sliced_relative_chop[l][0])
                    max_x = max(curve_sliced_relative_chop[l-1][0],curve_sliced_relative_chop[l][0])

                    this_profile = deepcopy(profile_height[np.where(profile_height[:,0]>=min_x)[0]])
                    this_profile = this_profile[np.where(max_x>=this_profile[:,0])[0]]


                    all_profile.append(this_profile)
                    this_mean_h=np.mean(this_profile[:,1])
                    ## using model to get the velocity
                    this_dh = h_target-this_mean_h
                    this_dh=max(0.01,this_dh) # to prevent inf or nan

                    this_v = dh2v_loglog(this_dh,mode=160)
                    this_v = min(max(min_v,this_v),max_v)

                    this_weld_v.append(this_v)
                    all_dh.append(this_dh)
                    seg_mean_h.append(this_mean_h)
                
                plt.scatter(profile_height[:,0],profile_height[:,1])
                plt.xlabel('x-axis (mm)',fontsize=26)
                plt.xticks(fontsize=26)
                plt.ylabel("Depoted Height (mm)",fontsize=26)
                plt.yticks(fontsize=26)
                plt.title('Deposition Height (mm)',fontsize=32)
                plt.grid(True, linestyle='--', alpha=0.7)  # Optional grid for better readability
                plt.show()
                
                # Create the figure and twin axes
                fig, ax1 = plt.subplots(figsize=(10, 6))
                ax2 = ax1.twinx()
                # Plot the data
                for v_id in range(len(this_weld_v)):
                    
                    if v_id == 0:
                        ax1.scatter(all_profile[v_id][:, 0], h_target - all_profile[v_id][:, 1], label=r'$\Delta h_d$ (dots)', s=100)  # Increase marker size
                        ax2.plot(all_profile[v_id][:, 0], np.ones(len(all_profile[v_id][:, 0])) * this_weld_v[v_id],
                                linewidth=2, label=f'Updated torch speed (lines)')  # Thicker line
                    else:
                        ax1.scatter(all_profile[v_id][:, 0], h_target - all_profile[v_id][:, 1], s=100)  # Increase marker size
                        plot_vx = np.append(all_profile[v_id - 1][-1, 0], all_profile[v_id][:, 0])
                        plot_vy = np.append(this_weld_v[v_id - 1], np.ones(len(all_profile[v_id][:, 0])) * this_weld_v[v_id])
                        ax2.plot(plot_vx, plot_vy, linewidth=2)  # Thicker line
                # Customize the axes
                ax1.set_xlabel('x-axis (mm)', fontsize=26, weight='bold')
                ax1.tick_params(axis='x', labelsize=22)
                ax1.set_ylabel(r'Deposition height $\Delta h_d$ (mm)', color='g', fontsize=26, weight='bold')
                ax1.tick_params(axis='y', labelsize=22, colors='g')
                ax2.set_ylabel('Torch speed (mm/sec)', color='b', fontsize=26, weight='bold')
                ax2.tick_params(axis='y', labelsize=22, colors='b')
                # Add a title
                plt.title(r'Desired Deposition Height $\Delta h_d$ vs Torch Speed, 40 MoveL', fontsize=32, weight='bold')
                # Add a legend
                lines_1, labels_1 = ax1.get_legend_handles_labels()
                lines_2, labels_2 = ax2.get_legend_handles_labels()
                ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper center', fontsize=22)
                # Show the plot
                plt.grid(True, linestyle='--', alpha=0.7)  # Optional grid for better readability
                plt.tight_layout()
                plt.show()
                
            ### plot velocity and actual velocity
            next_weld_dir=data_dir+'layer_'+str(i+1)+'/'
            next_weld_q=np.loadtxt(next_weld_dir+'weld_js_exe.csv',delimiter=',')
            next_weld_stamp=np.loadtxt(next_weld_dir+'weld_robot_stamps.csv',delimiter=',')
            next_scan_dir=next_weld_dir+'scans/'
            next_profile_height = np.load(next_scan_dir+'height_profile.npy')
            
            robot_p_S1TCP=[]
            for q in next_weld_q:
                r_tcp=robot_weld.fwd(q[:6])
                r_S1TCP=Transform(T_S1TCP_R1Base[:3,:3],T_S1TCP_R1Base[:3,-1])*r_tcp
                robot_p_S1TCP.append(r_S1TCP.p)
            robot_p_S1TCP=np.array(robot_p_S1TCP)

            # start_idx=0
            # end_idx=-2
            plan_x = np.array(curve_sliced_relative)[:,0]
            plan_y = np.array(curve_sliced_relative)[:,1]
            
            robot_v_S1TCP=np.linalg.norm(np.diff(robot_p_S1TCP,axis=0),2,1)/np.diff(next_weld_stamp)
            robot_v_S1TCP=np.append(robot_v_S1TCP[0],robot_v_S1TCP)
            robot_v_S1TCP=moving_average(robot_v_S1TCP,padding=True)
            robot_a_S1TCP=np.gradient(robot_v_S1TCP)/np.gradient(next_weld_stamp)
            robot_a_S1TCP=moving_average(robot_a_S1TCP,padding=True)

            start_idx=300
            end_idx=np.where(robot_v_S1TCP==0)[0][-1]
            robot_p_S1TCP=robot_p_S1TCP[start_idx:end_idx+1]
            next_weld_stamp=next_weld_stamp[start_idx:end_idx+1]
            robot_v_S1TCP=robot_v_S1TCP[start_idx:end_idx+1]
            robot_a_S1TCP=robot_a_S1TCP[start_idx:end_idx+1]

            dh_in_layer = []
            for curve_i in range(len(next_profile_height)):
                px=next_profile_height[curve_i,0]
                this_l_id=np.argmin(np.fabs(profile_height[:,0]-px))
                dh_in_layer.append([px,next_profile_height[curve_i,1]-profile_height[this_l_id,1]])
            dh_in_layer=np.array(dh_in_layer)

            motion_dh = []
            for curve_i in range(len(robot_p_S1TCP)):
                px=robot_p_S1TCP[curve_i,0]
                this_l_id=np.argmin(np.fabs(profile_height[:,0]-px))
                motion_dh.append([px,robot_p_S1TCP[curve_i,2]-profile_height[this_l_id,1]])
            motion_dh=np.array(motion_dh)

            all_profile_plot=[]
            all_profile_v_plot=[]
            for seg_i in range(len(all_profile)):
                p=deepcopy(all_profile[seg_i])
                all_profile_plot.extend(all_profile[seg_i])
                all_profile_v_plot.extend(np.array([p[:,0],np.repeat(this_weld_v[seg_i],len(p[:,0]))]).T)
            all_profile_plot=np.array(all_profile_plot)
            all_profile_v_plot=np.array(all_profile_v_plot)

        forward_flag= not forward_flag

        all_h_mean.append(np.mean(profile_height[start_id:end_id,1]))

        all_h_std.append(np.std(profile_height[start_id:end_id,1]))

    i=0
    m_size=12
    # print('all_correction_layer',all_correction_layer)
    # print('all_profile_height',all_profile_height)
    for profile_height in all_profile_height:
        if i in all_correction_layer:
            if i==all_correction_layer[0]:
                plt.scatter(profile_height[start_id:end_id,0],profile_height[start_id:end_id,1],s=3,c='tab:green',label='Corrected Layer')
            else:
                plt.scatter(profile_height[start_id:end_id,0],profile_height[start_id:end_id,1],s=3,c='tab:green')
        else:
            if i==0:
                plt.scatter(profile_height[start_id:end_id,0],profile_height[start_id:end_id,1],s=3,c='tab:blue',label='Forward (Right to Left)')
            elif i==1:
                plt.scatter(profile_height[start_id:end_id,0],profile_height[start_id:end_id,1],s=3,c='tab:orange',label='Backward (Left to Right)')
            elif i%2==0:
                plt.scatter(profile_height[start_id:end_id,0],profile_height[start_id:end_id,1],s=3,c='tab:blue')
            else:
                plt.scatter(profile_height[start_id:end_id,0],profile_height[start_id:end_id,1],s=3,c='tab:orange')
        i+=1
    plt.xlabel('x-axis')
    plt.ylabel('z-axis')
    plt.legend()
    plt.title("Height Profile")
    plt.tight_layout()
    plt.show()

    datasets_h_mean[dataset]=np.array(all_h_mean)
    datasets_h_std[dataset]=np.array(all_h_std)

for dataset in datasets:
    plt.plot(np.arange(len(datasets_h_mean[dataset])),datasets_h_mean[dataset],'-o',label=dataset)
plt.legend()
plt.xlabel('Layer')
plt.ylabel('Mean Height (mm)')
plt.title("Mean Height")
plt.tight_layout()
plt.show()

print("Average/Std of height std")
for dataset in datasets:
    plt.plot(np.arange(len(datasets_h_std[dataset])),datasets_h_std[dataset],'-o',label=dataset)
    print(dataset,':',round(np.mean(datasets_h_std[dataset]),5),round(np.std(datasets_h_std[dataset]),5))
# plt.axhline(y = 0.48, color = 'r', linestyle = '-')
plt.legend(fontsize=12)
plt.xlabel('Layer',fontsize=15)
plt.xticks(fontsize=15)
plt.ylabel('Height STD (mm)',fontsize=15)
plt.yticks(fontsize=12)
plt.title("Height STD",fontsize=18)
plt.tight_layout()
plt.show()
print("==================")

datasets_dh_mean={}
for dataset in datasets:
    datasets_dh_mean[dataset] = np.diff(datasets_h_mean[dataset])
    datasets_dh_mean[dataset] = np.append(datasets_h_mean[dataset][0],datasets_dh_mean[dataset])
    plt.plot(np.arange(len(datasets_dh_mean[dataset])),datasets_h_std[dataset]/datasets_dh_mean[dataset]*100,'-o',label=dataset)
plt.legend()
plt.xlabel('Layer')
plt.ylabel('Height STD/Mean dh (%)')
plt.title("Height STD/Mean dh (%)")
plt.tight_layout()
plt.show()