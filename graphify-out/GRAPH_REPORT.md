# Graph Report - .  (2026-04-11)

## Corpus Check
- 161 files · ~1,347,443 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 843 nodes · 1159 edges · 58 communities detected
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 50 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `AnimationControllerPy` - 38 edges
2. `HailoAsyncInference` - 15 edges
3. `HailoInfer` - 15 edges
4. `AudioPlayerAsync` - 15 edges
5. `main()` - 14 edges
6. `qToFloat()` - 14 edges
7. `WebSocketRobotServer` - 13 edges
8. `TestInterpolation` - 13 edges
9. `Pupper MJX RL Training` - 13 edges
10. `HailoDetectionNode` - 12 edges

## Surprising Connections (you probably didn't know these)
- `WandB Policy Download Script` --conceptually_related_to--> `Pupper MJX RL Training`  [INFERRED]
  ros2_ws/src/neural_controller/README.md → ai/rl/README.md
- `Interactive Blue Eyes SVG with Gaze Tracking` --conceptually_related_to--> `Blue Eyes Mascot Icon for Pupper Desktop App`  [INFERRED]
  ros2_ws/src/openai_bridge/openai_bridge/eyes.svg → pupper-rs/src/blue_eyes.png
- `From depth_estimation.cpp in Hailo-Application-Code-Examples          Gives a pr` --uses--> `HailoInfer`  [INFERRED]
  ros2_ws/src/hailo/hailo/hailo_depth.py → ros2_ws/src/hailo/hailo/hailo_inference.py
- `Clip depth values to be within the specified percentiles.` --uses--> `HailoInfer`  [INFERRED]
  ros2_ws/src/hailo/hailo/hailo_depth.py → ros2_ws/src/hailo/hailo/hailo_inference.py
- `Convert detections dictionary to ROS Detection2DArray and MarkerArray messages.` --uses--> `HailoAsyncInference`  [INFERRED]
  ros2_ws/src/hailo/hailo/hailo_detection.py → ros2_ws/src/hailo/hailo/utils.py

## Hyperedges (group relationships)
- **ros2_control Hardware-Simulator Pipeline** — ros2_control_framework, control_board_hw_if, mujoco_hw_interface, neural_controller_pkg, real2sim_controller_pkg [EXTRACTED 0.90]
- **Pupper Feelings Face Animation Set** — face_animation_regular_eyes, face_animation_fancy_eyes, face_animation_fancy_eyes_left, face_animation_fancy_eyes_right, face_animation_fancy_eyes_up, face_animation_fancy_eyes_down, face_animation_heart_eyes, face_animation_dog, face_animation_ask [EXTRACTED 1.00]
- **JAX/MJX RL Training Toolchain** — jax_framework, mujoco_sim_lib, mujoco_mjx_lib, brax_lib, flax_lib, orbax_lib, hydra_config, wandb_tracker [EXTRACTED 0.95]
- **Fisheye Camera Image Dataset for Hailo** — camera_fisheye_indoor_room1, camera_fisheye_living_room, camera_fisheye_lab_person, camera_fisheye_low_angle_feet, camera_fisheye_person_doorway [INFERRED 0.85]
- **Pupper-rs Status Icon Set** — status_unknown, status_active, status_inactive, status_loading [EXTRACTED 1.00]
- **Pupper V3 Visual Identity - Blue Eyes** — eyes_svg, blue_eyes_png [INFERRED 0.75]

## Communities

### Community 0 - "Animation Controller"
Cohesion: 0.04
Nodes (36): AnimationControllerPy, main(), Load all CSV animation files from the animation_controller_py package., Load animation data from a CSV file using pandas., Handle joint states updates., Python implementation of animation controller that publishes to forward command, Handle animation selection requests., Switch from neural controllers to forward command controllers. (+28 more)

### Community 1 - "MuJoCo Interactive Core"
Cohesion: 0.06
Nodes (46): actuator_position(), actuator_velocity(), alignscale(), base_angular_velocity(), base_orientation(), base_position(), base_velocity(), calibrate_motors_blocking() (+38 more)

### Community 2 - "Hailo Object Detection"
Cohesion: 0.06
Nodes (22): HailoDetectionNode, main(), Convert detections dictionary to ROS Detection2DArray and MarkerArray messages., Publish detection bounding boxes and IDs over ZMQ as JSON., Extract detections from YOLOv8 results., divide_list_to_batches(), DoStuffOnDestruction, HailoAsyncInference (+14 more)

### Community 3 - "Bag Recorder Node"
Cohesion: 0.07
Nodes (18): BagRecorderNode, main(), Stop the current bag recording., Handle joystick input., Cleanup when node is destroyed., Get all topics except those containing raw images., Start MCAP bag recording with filtered topics., DualShockServoController (+10 more)

### Community 4 - "OpenAI Audio Bridge"
Cohesion: 0.08
Nodes (10): AudioPlayerAsync, send_audio_worker_sounddevice(), async_input(), get_input(), # TODO: fix bug in interruption code that would prevent openai from speaking bac, RealtimeAPIClient, together(), activate() (+2 more)

### Community 5 - "MuJoCo Simulation Utils"
Cohesion: 0.11
Nodes (26): alignscale(), cleartimers(), copycamera(), copykey(), getSavePath(), infotext(), init(), loadmodel() (+18 more)

### Community 6 - "Hailo Depth Estimation"
Cohesion: 0.07
Nodes (15): HailoDepth, main(), From depth_estimation.cpp in Hailo-Application-Code-Examples          Gives a pr, Clip depth values to be within the specified percentiles., HailoInfer, Get a HEF instance          Returns:             HEF: A HEF (Hailo Executable Fi, Get the shape of the model's input layer.          Returns:             Tuple[in, Run an asynchronous inference job on a batch of preprocessed inputs.          Th (+7 more)

### Community 7 - "Pupper-rs Configuration"
Cohesion: 0.08
Nodes (14): BagRecorderConfig, BatteryConfig, BlinkConfig, Config, CpuConfig, EyeTrackingConfig, EyeTrackingMode, EyeTrackingSource (+6 more)

### Community 8 - "Rust Bag Recorder"
Cohesion: 0.07
Nodes (15): BagRecorderMonitor, BagRecorderStatus, query_bag_recording_status(), Controller Manager Services, draw_eyebrow(), quadratic_bezier_points(), EStopController, /joy Topic (+7 more)

### Community 9 - "RL Training Pipeline"
Cohesion: 0.1
Nodes (19): check_gpu(), main(), ModelManager, Handles model setup and modifications., Clone and setup required repositories., Modify robot model and return path to modified model., Add height field to the model., Handles the training process. (+11 more)

### Community 10 - "Fisheye Camera Utils"
Cohesion: 0.1
Nodes (20): bounding_box_to_rays(), CameraModel, convert_boxes_to_elevation_heading(), create_equirectangular_rays(), create_fisheye_model_from_params(), DoubleSphereModel, equirectangular_pixel_to_elevation_heading(), equirectangular_pixel_to_ray() (+12 more)

### Community 11 - "BNO055 IMU Driver"
Cohesion: 0.15
Nodes (27): BNO055(), dataAvailable(), enableAccelerometer(), enableGyro(), enableLinearAccelerometer(), enableRotationVector(), getAccelX(), getAccelY() (+19 more)

### Community 12 - "ROS2 Launch Files"
Cohesion: 0.07
Nodes (0): 

### Community 13 - "Control Board Hardware Interface"
Cohesion: 0.12
Nodes (17): contains_nan(), ~ControlBoardHardwareInterface(), copy_actuator_commands(), copy_actuator_states(), deactivate_motors(), do_homing(), hw_states_contains_nan(), on_activate() (+9 more)

### Community 14 - "ROS2 Package Descriptions"
Cohesion: 0.1
Nodes (27): Battery Monitoring Script, BNO055 IMU Sensor, CANbus Cheetah Protocol, cmd_vel_mux Package, /cmd_vel Topic, control_board_hardware_interface Package, GLFW3 (3.3), imu_to_tf Package (+19 more)

### Community 15 - "LLM WebSocket Server"
Cohesion: 0.12
Nodes (12): main(), Process commands from the queue sequentially., Add request_id to response if provided., Handle specific robot commands and return appropriate responses., Activate the robot by switching to the default controller., Deactivate the robot by stopping all controllers., Move the robot with the specified velocities., Get battery percentage and voltage using the existing battery check script. (+4 more)

### Community 16 - "Actuator Model"
Cohesion: 0.12
Nodes (5): ActuatorModelInterface, PIDActuatorModel, FixedSizeQueue, ~MujocoHardwareInterface(), on_deactivate()

### Community 17 - "RL Training Dependencies"
Cohesion: 0.16
Nodes (17): Brax (0.12.1), Flax (0.10.2), Height Field Randomization, Hydra Configuration, JAX (0.5.0), ModelManager Class, MuJoCo-MJX (3.2.7), MuJoCo (3.2.7) (+9 more)

### Community 18 - "Face Animations & Eyes"
Cohesion: 0.16
Nodes (16): Blue Eyes Mascot Icon for Pupper Desktop App, Interactive Blue Eyes SVG with Gaze Tracking, Ask/Question Face Animation, Dog Face Animation, Fancy Eyes Animation, Fancy Eyes Down Animation, Fancy Eyes Left Animation, Fancy Eyes Right Animation (+8 more)

### Community 19 - "Face Control GUI"
Cohesion: 0.23
Nodes (5): Colors, JoyListener, main(), open_desktop_terminal(), Opens a new xterm on the Pi desktop (DISPLAY=:0) that will display     whatever

### Community 20 - "Person Follower"
Cohesion: 0.19
Nodes (7): main(), PersonFollowerNode, Main control loop for visual servoing., Stop the robot by publishing zero velocities., Handle activation service request., Handle deactivation service request., Process detection messages.

### Community 21 - "Neural Controller"
Cohesion: 0.16
Nodes (4): check_param_vector_size(), NeuralController(), on_init(), MuJoCo Simulation Screenshot of Pupper V3

### Community 22 - "OpenAI Realtime Client"
Cohesion: 0.28
Nodes (4): async_input(), get_input(), RealtimeAPIClient, together()

### Community 23 - "LLM Service Monitor"
Cohesion: 0.21
Nodes (6): LlmServiceMonitor, LlmServiceStatus, query_llm_status(), query_robot_status(), ServiceMonitor, ServiceStatus

### Community 24 - "Face Control (Rust)"
Cohesion: 0.27
Nodes (3): Colors, JoyListener, main()

### Community 25 - "Real2Sim Controller"
Cohesion: 0.22
Nodes (3): binary_sign(), Real2SimController(), update()

### Community 26 - "UI Tools"
Cohesion: 0.31
Nodes (7): uiKeyboard(), uiModify(), uiMouseButton(), uiMouseMove(), uiResize(), uiScroll(), uiUpdateState()

### Community 27 - "SPI Bus Interface"
Cohesion: 0.33
Nodes (8): fake_spine_control(), init_spi(), spi_driver_run(), spi_open(), spi_send_receive(), spi_to_spine(), spine_to_spi(), xor_checksum()

### Community 28 - "Mock Camera"
Cohesion: 0.24
Nodes (5): main(), MockCameraNode, Callback to cycle to the next image., Publish the current image in both raw and compressed formats., Load all images from the configured folder.

### Community 29 - "Detection Receiver"
Cohesion: 0.29
Nodes (3): DetectionReceiver, PeopleDetections, PersonLocation

### Community 30 - "WebSocket Client Tests"
Cohesion: 0.47
Nodes (5): interactive_mode(), main(), Test various robot commands via WebSocket., Interactive mode for manual testing., test_commands()

### Community 31 - "MuJoCo Basic Sample"
Cohesion: 0.33
Nodes (0): 

### Community 32 - "Battery Monitor"
Cohesion: 0.47
Nodes (2): BatteryMonitor, query_battery_percentage()

### Community 33 - "CPU Monitor"
Cohesion: 0.33
Nodes (1): CpuMonitor

### Community 34 - "Blink Animation"
Cohesion: 0.47
Nodes (1): BlinkState

### Community 35 - "RL Policy Utilities"
Cohesion: 0.4
Nodes (2): # TODO: This introduces a fundamental limit to the policy performance, # NOTE: without a body collision geometry, can't train recovery policy

### Community 36 - "Fisheye Camera Images"
Cohesion: 0.4
Nodes (5): Fisheye Camera Image - Indoor Room with Equipment, Fisheye Camera Image - Lab Environment with Standing Person, Fisheye Camera Image - Living Room with Person and Sofa, Fisheye Camera Image - Low Angle View of Feet, Fisheye Camera Image - Person Near Doorway

### Community 37 - "MuJoCo XML Compiler"
Cohesion: 0.83
Nodes (3): filetype(), finish(), main()

### Community 38 - "IMU to TF Publisher"
Cohesion: 0.5
Nodes (1): ImuToTf

### Community 39 - "Cmd Vel Mux"
Cohesion: 0.5
Nodes (1): CmdVelMux

### Community 40 - "Status Icons"
Cohesion: 0.5
Nodes (4): Status Active Icon - Green Circle, Status Inactive Icon - Red Circle, Status Loading Icon - Orange Circle, Status Unknown Icon - Gray Circle

### Community 41 - "RL Config Tests"
Cohesion: 0.67
Nodes (2): Test configuration loading., test_config()

### Community 42 - "Policy Download"
Cohesion: 0.67
Nodes (2): download_latest_model(), Downloads the latest model from a W&B project.      :param project_name: The nam

### Community 43 - "Flake8 Lint Tests"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "Copyright Tests"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "PEP257 Doc Tests"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "MuJoCo XML Generator"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Mesh Rename Utils"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "URDF Fix Utils"
Cohesion: 1.0
Nodes (0): 

### Community 49 - "COCO Classes Config"
Cohesion: 1.0
Nodes (1): COCO Object Detection Classes (80 classes)

### Community 50 - "RL Rationale (GPU)"
Cohesion: 1.0
Nodes (1): Check GPU availability.

### Community 51 - "RL Rationale (Env)"
Cohesion: 1.0
Nodes (1): Verify MuJoCo installation.

### Community 52 - "RL Rationale (Domain)"
Cohesion: 1.0
Nodes (1): Setup environment variables.

### Community 53 - "Setup Script"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Init Module"
Cohesion: 1.0
Nodes (0): 

### Community 55 - "RL Requirements"
Cohesion: 1.0
Nodes (1): RL Training Dependencies

### Community 56 - "Joy Utils"
Cohesion: 1.0
Nodes (1): joy_utils Package

### Community 57 - "Fullscreen Icon"
Cohesion: 1.0
Nodes (1): Fullscreen Toggle UI Icon

## Knowledge Gaps
- **137 isolated node(s):** `Handles system validation and setup.`, `Check GPU availability.`, `Verify MuJoCo installation.`, `Setup environment variables.`, `Handles model setup and modifications.` (+132 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Flake8 Lint Tests`** (2 nodes): `test_flake8.py`, `test_flake8()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Copyright Tests`** (2 nodes): `test_copyright.py`, `test_copyright()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `PEP257 Doc Tests`** (2 nodes): `test_pep257.py`, `test_pep257()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `MuJoCo XML Generator`** (2 nodes): `create_mujoco_xml.py`, `compose_robot_xml()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Mesh Rename Utils`** (2 nodes): `rename_meshes.py`, `remove_spaces_from_filenames()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `URDF Fix Utils`** (2 nodes): `fix_urdf.py`, `fix_mesh_paths()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `COCO Classes Config`** (1 nodes): `COCO Object Detection Classes (80 classes)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `RL Rationale (GPU)`** (1 nodes): `Check GPU availability.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `RL Rationale (Env)`** (1 nodes): `Verify MuJoCo installation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `RL Rationale (Domain)`** (1 nodes): `Setup environment variables.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Setup Script`** (1 nodes): `setup.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init Module`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `RL Requirements`** (1 nodes): `RL Training Dependencies`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Joy Utils`** (1 nodes): `joy_utils Package`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Fullscreen Icon`** (1 nodes): `Fullscreen Toggle UI Icon`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HailoDetectionNode` connect `Hailo Object Detection` to `Bag Recorder Node`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Why does `AnimationControllerPy` connect `Animation Controller` to `Bag Recorder Node`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 23 inferred relationships involving `AnimationControllerPy` (e.g. with `TestAnimationController` and `TestCSVLoading`) actually correct?**
  _`AnimationControllerPy` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `HailoAsyncInference` (e.g. with `HailoDetectionNode` and `Convert detections dictionary to ROS Detection2DArray and MarkerArray messages.`) actually correct?**
  _`HailoAsyncInference` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `HailoInfer` (e.g. with `HailoDepth` and `From depth_estimation.cpp in Hailo-Application-Code-Examples          Gives a pr`) actually correct?**
  _`HailoInfer` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `AudioPlayerAsync` (e.g. with `RealtimeAPIClient` and `# TODO: fix bug in interruption code that would prevent openai from speaking bac`) actually correct?**
  _`AudioPlayerAsync` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Handles system validation and setup.`, `Check GPU availability.`, `Verify MuJoCo installation.` to the rest of the system?**
  _137 weakly-connected nodes found - possible documentation gaps or missing edges._