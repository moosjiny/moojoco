#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, Point
from visualization_msgs.msg import InteractiveMarker, InteractiveMarkerControl, Marker, InteractiveMarkerFeedback
from interactive_markers.interactive_marker_server import InteractiveMarkerServer

class DualArmInteractiveMarker(Node):
    def __init__(self):
        super().__init__('dual_arm_interactive_marker')
        
        # Publishers to send pose commands to MuJoCo
        self.pub_left = self.create_publisher(PoseStamped, '/target_left/pose_cmd', 10)
        self.pub_right = self.create_publisher(PoseStamped, '/target_right/pose_cmd', 10)
        
        # State tracking
        self.is_dragging = {"target_left": False, "target_right": False}
        
        # Subscriptions for actual hand poses from MuJoCo (to snap markers back)
        self.sub_left_hand = self.create_subscription(
            PoseStamped, '/target_left/hand_pose', self.left_hand_callback, 10)
        self.sub_right_hand = self.create_subscription(
            PoseStamped, '/target_right/hand_pose', self.right_hand_callback, 10)
        
        # Create Interactive Marker Server
        self.server = InteractiveMarkerServer(self, 'dual_arm_markers')
        
        # Create Left Target Marker (Initial position of left hand)
        self.create_marker("target_left", [0.0, -0.541, 0.773], [1.0, 0.0, 0.0])
        # Create Right Target Marker (Initial position of right hand)
        self.create_marker("target_right", [0.0, 0.541, 0.773], [0.0, 0.0, 1.0])
        
        self.server.applyChanges()
        
        # Throttle synchronization to 5Hz to prevent RViz flickering
        self.last_sync_left = self.get_clock().now()
        self.last_sync_right = self.get_clock().now()
        
        self.get_logger().info("Interactive Marker Server Started with Throttled Sync!")

    def create_marker(self, name, position, color):
        int_marker = InteractiveMarker()
        int_marker.header.frame_id = "world"
        int_marker.name = name
        int_marker.description = f"{name} Control"
        
        int_marker.pose.position.x = position[0]
        int_marker.pose.position.y = position[1]
        int_marker.pose.position.z = position[2]
        
        # Create a visual marker (sphere) for the center
        sphere_marker = Marker()
        sphere_marker.type = Marker.SPHERE
        sphere_marker.scale.x = 0.08
        sphere_marker.scale.y = 0.08
        sphere_marker.scale.z = 0.08
        sphere_marker.color.r = color[0]
        sphere_marker.color.g = color[1]
        sphere_marker.color.b = color[2]
        sphere_marker.color.a = 0.5
        
        sphere_control = InteractiveMarkerControl()
        sphere_control.always_visible = True
        sphere_control.markers.append(sphere_marker)
        int_marker.controls.append(sphere_control)
        
        # Add XYZ Translation Controls (Arrows)
        control_x = InteractiveMarkerControl()
        control_x.name = "move_x"
        control_x.interaction_mode = InteractiveMarkerControl.MOVE_AXIS
        control_x.orientation.w = 1.0
        control_x.orientation.x = 1.0
        control_x.orientation.y = 0.0
        control_x.orientation.z = 0.0
        int_marker.controls.append(control_x)
        
        control_y = InteractiveMarkerControl()
        control_y.name = "move_y"
        control_y.interaction_mode = InteractiveMarkerControl.MOVE_AXIS
        control_y.orientation.w = 1.0
        control_y.orientation.x = 0.0
        control_y.orientation.y = 1.0
        control_y.orientation.z = 0.0
        int_marker.controls.append(control_y)
        
        control_z = InteractiveMarkerControl()
        control_z.name = "move_z"
        control_z.interaction_mode = InteractiveMarkerControl.MOVE_AXIS
        control_z.orientation.w = 1.0
        control_z.orientation.x = 0.0
        control_z.orientation.y = 0.0
        control_z.orientation.z = 1.0
        int_marker.controls.append(control_z)
        
        self.server.insert(int_marker, feedback_callback=self.process_feedback)

    def left_hand_callback(self, msg):
        now = self.get_clock().now()
        if (now - self.last_sync_left).nanoseconds > 200_000_000: # 5Hz
            if not self.is_dragging["target_left"]:
                self.server.setPose("target_left", msg.pose)
                self.server.applyChanges()
                self.last_sync_left = now

    def right_hand_callback(self, msg):
        now = self.get_clock().now()
        if (now - self.last_sync_right).nanoseconds > 200_000_000: # 5Hz
            if not self.is_dragging["target_right"]:
                self.server.setPose("target_right", msg.pose)
                self.server.applyChanges()
                self.last_sync_right = now

    def process_feedback(self, feedback):
        if feedback.event_type == InteractiveMarkerFeedback.POSE_UPDATE:
            self.is_dragging[feedback.marker_name] = True
            msg = PoseStamped()
            msg.header = feedback.header
            msg.pose = feedback.pose
            if feedback.marker_name == "target_left":
                self.pub_left.publish(msg)
            elif feedback.marker_name == "target_right":
                self.pub_right.publish(msg)
        elif feedback.event_type == InteractiveMarkerFeedback.MOUSE_UP:
            self.is_dragging[feedback.marker_name] = False
        elif feedback.event_type == InteractiveMarkerFeedback.MOUSE_DOWN:
            self.is_dragging[feedback.marker_name] = True

def main(args=None):
    rclpy.init(args=args)
    node = DualArmInteractiveMarker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
