import math
import threading
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from geometry_msgs.msg import TwistStamped, Pose2D
from nav_msgs.msg import Odometry
from tf_transformations import euler_from_quaternion
from tb3_interfaces.srv import MoveToPose


class RobotController(Node):

    def __init__(self):
        super().__init__('move_to_pose_node')

        # Where the robot is right now
        self.x   = 0.0
        self.y   = 0.0
        self.yaw = 0.0

        # Where the robot needs to go
        self.goal_x   = 0.0
        self.goal_y   = 0.0
        self.goal_yaw = 0.0

        # Is the robot currently moving to a goal?
        self.moving = False

        # This lets the service wait without freezing everything else
        self.done = threading.Event()

        # Allow service and timer to run at the same time
        group = ReentrantCallbackGroup()

        # Listen to robot position
        self.create_subscription(
            Odometry,
            '/odom',
            self.got_odom,
            10,
            callback_group=group
        )

        # Listen for a goal via topic
        self.create_subscription(
            Pose2D,
            '/goal_pose',
            self.got_goal_topic,
            10,
            callback_group=group
        )

        # Send speed commands to robot
        self.speed_pub = self.create_publisher(TwistStamped, '/cmd_vel', 10)

        # Offer the move_to_pose service
        self.create_service(
            MoveToPose,
            'move_to_pose',
            self.got_goal_service,
            callback_group=group
        )

        # Run the controller 10 times per second
        self.create_timer(0.1, self.control_loop, callback_group=group)

        self.get_logger().info('Robot controller ready!')
        self.get_logger().info('Send a goal via service or /goal_pose topic')


    def got_odom(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y

        q = msg.pose.pose.orientation
        _, _, self.yaw = euler_from_quaternion([q.x, q.y, q.z, q.w])


    def got_goal_topic(self, msg):
        # Goal received via topic - no reply needed
        self.goal_x   = msg.x
        self.goal_y   = msg.y
        self.goal_yaw = math.radians(msg.theta)
        self.moving   = True

        self.get_logger().info(
            f'Topic goal: x={msg.x} y={msg.y} yaw={msg.theta} degrees'
        )


    def got_goal_service(self, request, response):
        # Goal received via service - must send back a reply

        self.get_logger().info(
            f'Service goal: x={request.x} y={request.y} yaw={request.yaw_deg} degrees'
        )

        # Set the goal
        self.goal_x   = request.x
        self.goal_y   = request.y
        self.goal_yaw = math.radians(request.yaw_deg)

        # Clear the done signal and start moving
        self.done.clear()
        self.moving = True

        # Wait here until control_loop signals we are done
        # This blocks only this thread - everything else keeps running
        reached = self.done.wait(timeout=60.0)

        if reached:
            response.success = True
            response.message = (
                f'Reached goal: x={request.x} y={request.y} '
                f'yaw={request.yaw_deg} degrees'
            )
        else:
            self.moving = False
            self.send_speed(0.0, 0.0)
            response.success = False
            response.message = 'Timed out before reaching goal'

        return response


    def control_loop(self):
        if not self.moving:
            return

        # How far away is the goal?
        dx = self.goal_x - self.x
        dy = self.goal_y - self.y
        distance = math.sqrt(dx**2 + dy**2)

        # What direction is the goal?
        angle_to_goal = math.atan2(dy, dx)

        # How much to turn to face the goal?
        heading_error = self.normalize(angle_to_goal - self.yaw)

        # How far off is the final angle?
        orientation_error = self.normalize(self.goal_yaw - self.yaw)

        # Are we close enough to stop?
        if distance < 0.05 and abs(orientation_error) < math.radians(5):
            self.send_speed(0.0, 0.0)
            self.moving = False
            self.get_logger().info('Reached goal!')
            # Signal the service that we are done
            self.done.set()
            return

        # Calculate speeds
        if distance >= 0.05:
            forward = 0.5 * distance
            turn    = 1.5 * heading_error
        else:
            forward = 0.0
            turn    = 1.5 * orientation_error

        # Clamp to safe limits
        forward = max(-0.22, min(0.22, forward))
        turn    = max(-2.84, min(2.84, turn))

        self.send_speed(forward, turn)


    def send_speed(self, forward, turn):
        msg = TwistStamped()
        msg.header.stamp    = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.twist.linear.x  = forward
        msg.twist.angular.z = turn
        self.speed_pub.publish(msg)


    def normalize(self, angle):
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle


def main(args=None):
    rclpy.init(args=args)
    node = RobotController()

    # MultiThreadedExecutor lets the service wait
    # while the control loop keeps running
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)

    executor.spin()

    node.destroy_node()
    rclpy.shutdown()
