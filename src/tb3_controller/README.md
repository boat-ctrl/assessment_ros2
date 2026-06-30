# TurtleBot3 Controller — Assessment

A ROS2 package that drives a TurtleBot3 robot to a target position
using a Proportional (P) Controller and a custom ROS2 service.

---

## What It Does

- Listens to the robot position on `/odom`
- Accepts a goal position via the `/move_to_pose` service
- Accepts a goal position via the `/goal_pose` topic
- Drives the robot smoothly to the goal
- Stops when within 5cm and 5 degrees of the target
- Returns a success or failure message via the service

---

## Workspace Structure

```
assessment_ws/
└── src/
    ├── tb3_interfaces/            — custom service definition
    │   ├── CMakeLists.txt
    │   ├── package.xml
    │   └── srv/
    │       └── MoveToPose.srv
    └── tb3_controller/            — the robot brain
        ├── README.md
        ├── setup.py
        ├── package.xml
        └── tb3_controller/
            ├── __init__.py
            └── move_to_pose_node.py
```

---

## Service Definition

File: `tb3_interfaces/srv/MoveToPose.srv`

```
float64 x        # target x position in meters
float64 y        # target y position in meters
float64 yaw_deg  # target facing angle in degrees
---
bool success     # true if robot reached the goal
string message   # description of the result
```

The `---` line separates the request (what you send) from the
response (what you get back).

---

## Dependencies

```bash
sudo apt install ros-jazzy-turtlebot3* -y
sudo apt install ros-jazzy-ros-gz -y
sudo apt install ros-jazzy-tf-transformations -y
```

---

## Build Instructions

```bash
cd ~/assessment_ws
colcon build
source install/setup.bash
```

---

## Run Instructions

### Terminal 1 — Start the Simulation

```bash
source /opt/ros/jazzy/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_gazebo empty_world.launch.py
```

Wait until the Gazebo window opens and the robot is visible.

### Terminal 2 — Start the Controller Node

```bash
source /opt/ros/jazzy/setup.bash
source ~/assessment_ws/install/setup.bash
ros2 run tb3_controller move_to_pose_node
```

You should see:
```
Robot controller ready!
Send a goal via service or /goal_pose topic
```

### Terminal 3 — Send a Goal via Service

```bash
source /opt/ros/jazzy/setup.bash
source ~/assessment_ws/install/setup.bash

ros2 service call /move_to_pose tb3_interfaces/srv/MoveToPose \
  "{x: 1.0, y: 0.5, yaw_deg: 45.0}"
```

The terminal will wait silently while the robot moves.
When the robot arrives you will see:

```
response:
  success=True
  message='Reached goal: x=1.0 y=0.5 yaw=45.0 degrees'
```

---

## Example Service Calls

```bash
# Drive forward 1 meter
ros2 service call /move_to_pose tb3_interfaces/srv/MoveToPose \
  "{x: 1.0, y: 0.0, yaw_deg: 0.0}"

# Diagonal position, face 45 degrees
ros2 service call /move_to_pose tb3_interfaces/srv/MoveToPose \
  "{x: 1.0, y: 0.5, yaw_deg: 45.0}"

# Return home
ros2 service call /move_to_pose tb3_interfaces/srv/MoveToPose \
  "{x: 0.0, y: 0.0, yaw_deg: 0.0}"

# Negative position, face 180 degrees
ros2 service call /move_to_pose tb3_interfaces/srv/MoveToPose \
  "{x: -1.0, y: 0.0, yaw_deg: 180.0}"

# Far diagonal, face 90 degrees
ros2 service call /move_to_pose tb3_interfaces/srv/MoveToPose \
  "{x: 2.0, y: 1.0, yaw_deg: 90.0}"
```

---

## Alternative — Send Goal via Topic

You can also send a goal without waiting for a reply:

```bash
ros2 topic pub --once /goal_pose geometry_msgs/msg/Pose2D \
  "{x: 1.0, y: 0.5, theta: 45.0}"
```

The robot starts moving immediately. No reply is sent back.

---

## Goal Format

| Field     | Unit    | Description                          |
|-----------|---------|--------------------------------------|
| x         | meters  | How far forward                      |
| y         | meters  | How far left                         |
| yaw_deg   | degrees | Which direction to face on arrival   |

---

## How It Works

### Control Loop
Every 0.1 seconds the controller:

```
1. Reads current robot position from /odom
2. Calculates distance to goal
3. Calculates angle to goal
4. Sends forward and turn speeds proportional to the errors
5. Stops when close enough and signals the service
```

### Control Law

```
forward speed = 0.5 x distance error
turning speed = 1.5 x heading error
```

### Two Phase Approach

```
Phase 1 — Approaching (distance > 5cm)
  Robot drives forward and steers at the same time
  Speed decreases naturally as distance shrinks

Phase 2 — Arrived at position (distance < 5cm)
  Robot stops moving forward
  Robot rotates in place to face the correct direction
```

### Stop Condition

The robot stops when BOTH of these are true:
- Distance to goal is less than 0.05 meters (5 cm)
- Angle error is less than 5 degrees

---

## Topics and Services

| Name            | Type                          | Direction | Purpose                  |
|-----------------|-------------------------------|-----------|--------------------------|
| /odom           | nav_msgs/Odometry             | Incoming  | Robot current position   |
| /goal_pose      | geometry_msgs/Pose2D          | Incoming  | Goal via topic           |
| /move_to_pose   | tb3_interfaces/srv/MoveToPose | Incoming  | Goal via service         |
| /cmd_vel        | geometry_msgs/TwistStamped    | Outgoing  | Speed commands to robot  |

---

## Why MultiThreadedExecutor

The service handler blocks and waits while the robot is moving.
Without MultiThreadedExecutor the control loop timer would freeze
while the service is waiting and the robot would never move.

MultiThreadedExecutor runs three threads simultaneously:
- Thread 1 — reads odometry
- Thread 2 — runs the control loop timer
- Thread 3 — handles the service and waits for completion

threading.Event is used to signal between the control loop
and the service handler without blocking the executor.

---

## Assumptions

- Robot operates on flat ground only
- No obstacles between start and goal
- Odometry position data is trusted completely
- Robot starts from rest when a new goal is received
- One goal is processed at a time

---

## Known Limitations

- No obstacle avoidance — robot will collide with walls
- Odometry drifts over long distances
- Robot can overshoot very close goals at speed
- Gains are hardcoded — may need tuning for different environments

---

## Troubleshooting

### Robot does not move
```bash
# Check cmd_vel is being published
ros2 topic echo /cmd_vel

# Check odom is coming in
ros2 topic echo /odom --once

# Check the service exists
ros2 service list | grep move_to_pose
```

### Service times out
- Make sure Gazebo is running and the robot is visible
- Make sure Terminal 2 shows the node is ready
- Check that odom is publishing with ros2 topic hz /odom

### Build errors
```bash
cd ~/assessment_ws
rm -rf build install log
colcon build
source install/setup.bash
```

---

## Author

Assessment Engineer
ROS2 Jazzy — Ubuntu 24.04
