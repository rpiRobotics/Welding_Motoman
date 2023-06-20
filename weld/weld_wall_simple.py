import sys
sys.path.append('../toolbox/')
from robot_def import *
from dx200_motion_program_exec_client import *

robot=robot_obj('MA2010_A0',def_path='../config/MA2010_A0_robot_default_config.yml',tool_file_path='../config/torch.csv',\
	pulse2deg_file_path='../config/MA2010_A0_pulse2deg_real.csv',d=15)

R=np.array([[-0.7071, 0.7071, -0.    ],
            [ 0.7071, 0.7071,  0.    ],
            [0.,      0.,     -1.    ]])
p_start=np.array([1610,-860,-260])
p_end=np.array([1610,-760,-260])
q_seed=np.radians([-35.4291,56.6333,40.5194,4.5177,-52.2505,-11.6546])


mp=mp=MotionProgram(ROBOT_CHOICE='RB1',pulse2deg=robot.pulse2deg, tool_num=12)
client=MotionProgramExecClient()

base_layer_height=2
layer_height=0.8

# for i in range(1,2):
# 	if i%2==0:
# 		p1=p_start+np.array([0,0,i*base_layer_height])
# 		p2=p_end+np.array([0,0,i*base_layer_height])
# 	else:
# 		p1=p_end+np.array([0,0,i*base_layer_height])
# 		p2=p_start+np.array([0,0,i*base_layer_height])

# 	q_init=np.degrees(robot.inv(p1,R,q_seed)[0])
# 	q_end=np.degrees(robot.inv(p2,R,q_seed)[0])
# 	mp.MoveJ(q_init,1,0)
# 	mp.setArc(True,cond_num=410)
# 	mp.MoveL(q_end,5,0)
# 	mp.setArc(False)
# 	client.execute_motion_program(mp)

for i in range(2,3):
	if i%2==0:
		p1=p_start+np.array([0,0,2*base_layer_height+i*layer_height])
		p2=p_end+np.array([0,0,2*base_layer_height+i*layer_height])
	else:
		p1=p_end+np.array([0,0,2*base_layer_height+i*layer_height])
		p2=p_start+np.array([0,0,2*base_layer_height+i*layer_height])

	q_init=np.degrees(robot.inv(p1,R,q_seed)[0])
	q_end=np.degrees(robot.inv(p2,R,q_seed)[0])
	mp.MoveJ(q_init,1,0)
	mp.setArc(True,cond_num=401)
	mp.MoveL(q_end,12,0)
	mp.setArc(False)
	client.execute_motion_program(mp)