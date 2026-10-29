"""Physical harness order, from the supplied Roboto Origin manual and robot.yaml."""
BRANCHES = {
    'can0': ('Left leg', [1, 2, 3, 4, 5, 6]),
    'can1': ('Waist · right leg', [13, 7, 8, 9, 10, 11, 12]),
    'can2': ('Left arm', [14, 15, 16, 17, 18]),
    'can3': ('Right arm', [19, 20, 21, 22, 23]),
}
NAMES = [
    'Left hip yaw', 'Left hip roll', 'Left hip pitch', 'Left knee',
    'Left ankle upper', 'Left ankle lower', 'Right hip yaw', 'Right hip roll',
    'Right hip pitch', 'Right knee', 'Right ankle upper', 'Right ankle lower',
    'Waist yaw', 'Left shoulder pitch', 'Left shoulder roll', 'Left shoulder yaw',
    'Left elbow', 'Left distal arm', 'Right shoulder pitch', 'Right shoulder roll',
    'Right shoulder yaw', 'Right elbow', 'Right distal arm',
]
JOINTS = [
    'left_thigh_yaw_joint', 'left_thigh_roll_joint', 'left_thigh_pitch_joint',
    'left_knee_joint', 'left_ankle_pitch_joint', 'left_ankle_roll_joint',
    'right_thigh_yaw_joint', 'right_thigh_roll_joint', 'right_thigh_pitch_joint',
    'right_knee_joint', 'right_ankle_pitch_joint', 'right_ankle_roll_joint',
    'torso_joint', 'left_arm_pitch_joint', 'left_arm_roll_joint', 'left_arm_yaw_joint',
    'left_elbow_pitch_joint', 'left_elbow_yaw_joint', 'right_arm_pitch_joint',
    'right_arm_roll_joint', 'right_arm_yaw_joint', 'right_elbow_pitch_joint',
    'right_elbow_yaw_joint',
]
MOTORS = [dict(id=i, master=i+16, bus=bus, name=NAMES[i-1], joint=JOINTS[i-1],
               model='J10010L' if i in [1,2,3,4,7,8,9,10,13] else 'J4340P')
          for bus, (_, ids) in BRANCHES.items() for i in ids]
