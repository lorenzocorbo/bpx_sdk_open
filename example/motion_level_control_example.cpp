#include "motion_level_control.h"
#include "bpx_sdk_version.h"

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <iostream>
#include <thread>

namespace {

// Ctrl+C 时与 kYawVelocity 中超时分支（原约 171 行）走相同退出路径。
std::atomic<bool> g_yaw_stop_from_sigint{false};

void on_sigint(int /*signum*/) {
    g_yaw_stop_from_sigint.store(true, std::memory_order_relaxed);
}

enum class DemoPhase {
    kWait,
    kStandUp,
    kYawVelocity,
    kZeroVelocity,
    kSitDown,
    kForward,
};

void printVersion() {
    std::cout
        << BPX_SDK_PROJECT_NAME
        << " version=" << BPX_SDK_PROJECT_VERSION
        << std::endl;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 1) {
        std::cerr << argv[0] << " does not accept command line arguments." << std::endl;
        return 1;
    }

    printVersion();

    bpx_sdk::MotionLevelControl motion_level_control;

    // Set the target robot IP.
    motion_level_control.setRobotIp(bpx_sdk::DEFAULT_SERVER_IP);

    // Set the local port for receiving robot state packets.
    motion_level_control.setRobotStateUploadPort(bpx_sdk::DEFAULT_CLIENT_ROBOT_STATE_UDP_PORT);

    // Set the local control connection port. Use 0 for automatic selection.
    motion_level_control.setTcpLocalPort(0);

    // Set the requested robot state upload rate.
    motion_level_control.setRobotStateUploadRate(100);

    // Set the motion command send rate and velocity control mode.
    motion_level_control.setMotionCommandRate(50);

    if (!motion_level_control.connect()) {
        std::cerr << "failed to connect motion level control" << std::endl;
        return 1;
    }

    std::signal(SIGINT, on_sigint);

    std::cout << "motion level control running" << std::endl;
    DemoPhase phase = DemoPhase::kWait;
    auto phase_start = std::chrono::steady_clock::now();
    bool phase_announced = false;

    // 增加前进-后退循环计数
    static int forward_backward_cycle_count = 0;
    static bool is_forward = true; // true: 前进, false: 后退

    while (true) {
        const auto now = std::chrono::steady_clock::now();
        const auto phase_elapsed = now - phase_start;
        uint8_t current_state = 0;
        uint8_t current_gait = 0;
        float max_vel[3] = {};
        const bool has_current_motion_state =
            motion_level_control.getCurrentMotionState(&current_state);
        const bool has_current_gait = motion_level_control.getCurrentGait(&current_gait);
        const bool has_max_velocity = motion_level_control.getMaxVelocity(max_vel);
        const bool has_motion_state = has_current_motion_state && has_current_gait && has_max_velocity;
        if (has_motion_state) {
            auto motionStateToString = [](uint8_t state) -> const char* {
                switch (state) {
                    case 0: return "LyingDown";
                    case 1: return "StandingUp";
                    case 2: return "Passive";
                    case 3: return "SitDown";
                    case 6: return "Motion";
                    default: return "Unknown";
                }
            };

            auto gaitToString = [](uint8_t gait) -> const char* {
                switch (gait) {
                    case 0: return "Walk";
                    case 3: return "Bipedal";
                    case 4: return "Flip";
                    case 6: return "WalkPhase";
                    case 7: return "PoseTracking";
                    case 8: return "Running";
                    case 10: return "WalkPeriod";
                    default: return "Unknown";
                }
            };

            std::cout << "motion_state=" << static_cast<uint32_t>(current_state)
                      << " (" << motionStateToString(current_state) << ")"
                      << " gait=" << static_cast<uint32_t>(current_gait)
                      << " (" << gaitToString(current_gait) << ")"
                      << " max_vel=(" << max_vel[0] << ", "
                      << max_vel[1] << ", " << max_vel[2] << ")"
                      << std::endl;
                 
        } else {
            if (!has_current_motion_state) {
                std::cerr << "error has_current_motion_state" << std::endl;
            }
            if (!has_current_gait) {
                std::cerr << "error has_current_gait" << std::endl;
            }
            if (!has_max_velocity) {
                std::cerr << "error has_max_velocity" << std::endl;
            }
        }

        switch (phase) {
            case DemoPhase::kWait:
                if (!phase_announced) {
                    // motion_level_control.setZeroPositionsFlag();
                    std::cout << "send zero-position command" << std::endl;
                    std::cout << "wait 1 second before sending commands" << std::endl;
                    phase_announced = true;
                }
                if (phase_elapsed >= std::chrono::seconds(1)) {
                    phase = DemoPhase::kStandUp;
                    phase_start = now;
                    phase_announced = false;
                }
                break;

            case DemoPhase::kStandUp:
                if (!phase_announced) {
                    std::cout << "send stand-up command" << std::endl;
                    phase_announced = true;
                }
                if (!motion_level_control.setStandUp()) {
                    std::cerr << "failed to send stand-up command" << std::endl;
                    return 1;
                }
                if (has_motion_state && current_state == 6) {
                    phase = DemoPhase::kYawVelocity;
                    // phase = DemoPhase::kForward;
                    phase_start = now;
                    phase_announced = false;
                    motion_level_control.setVelocityControlFlag(true);
                }
                else if (phase_elapsed >= std::chrono::seconds(5)) {
                    std::cerr << "error has_motion_state:" << has_motion_state << " current_state:" << current_state << "." << std::endl;
                }
                break;

            case DemoPhase::kYawVelocity: // 左转
            {
                const int max_seconds = 3600;
                if (!phase_announced) {
                    std::cout << "send yaw velocity command for " << max_seconds << " seconds" << std::endl;
                    phase_announced = true;
                }
                if (!motion_level_control.setVelocity(0.0f, 0.0f, 1.0f)) {
                    std::cerr << "failed to send yaw velocity command" << std::endl;
                    return 1;
                }
                const bool time_up = phase_elapsed >= std::chrono::seconds(max_seconds);
                const bool sigint_stop =
                    g_yaw_stop_from_sigint.exchange(false, std::memory_order_acq_rel);
                if (time_up || sigint_stop) {
                    phase = DemoPhase::kZeroVelocity;
                    // phase = DemoPhase::kForward;
                    phase_start = now;
                    phase_announced = false;
                    motion_level_control.setVelocityControlFlag(false);
                }
                break;
            }

            case DemoPhase::kForward: // 前进与后退循环
                if (!phase_announced) {
                    if (is_forward) {
                        std::cout << "send forward velocity command for 1 second (cycle " 
                                  << (forward_backward_cycle_count + 1) << "/5)" << std::endl;
                    } else {
                        std::cout << "send backward velocity command for 1 second (cycle " 
                                  << (forward_backward_cycle_count + 1) << "/5)" << std::endl;
                    }
                    phase_announced = true;
                }
                if (is_forward) {
                    if (!motion_level_control.setVelocity(0.5f, 0.0f, 0.0f)) {
                        std::cerr << "failed to send forward velocity command" << std::endl;
                        return 1;
                    }
                } else {
                    if (!motion_level_control.setVelocity(-0.5f, 0.0f, 0.0f)) {
                        std::cerr << "failed to send backward velocity command" << std::endl;
                        return 1;
                    }
                }
                if (phase_elapsed >= std::chrono::seconds(1)) {
                    // 如果完成一个前进，则开始后退；否则下一个cycle
                    if (is_forward) {
                        is_forward = false;
                        phase_start = now;
                        phase_announced = false;
                    } else {
                        is_forward = true;
                        forward_backward_cycle_count++;
                        phase_start = now;
                        phase_announced = false;
                    }
                    // 完成5个cycle后跳转到ZeroVelocity
                    if (forward_backward_cycle_count >= 5) {
                        phase = DemoPhase::kZeroVelocity;
                        phase_start = now;
                        phase_announced = false;
                        motion_level_control.setVelocityControlFlag(false);
                        // 归零计数器和状态
                        forward_backward_cycle_count = 0;
                        is_forward = true;
                    }
                }
                break;

            case DemoPhase::kZeroVelocity:
                if (!phase_announced) {
                    std::cout << "send zero velocity command for 2 seconds" << std::endl;
                    phase_announced = true;
                }
                if (!motion_level_control.setVelocity(0.0f, 0.0f, 0.0f)) {
                    std::cerr << "failed to send zero velocity command" << std::endl;
                    return 1;
                }
                if (phase_elapsed >= std::chrono::seconds(2)) {
                    phase = DemoPhase::kSitDown;
                    phase_start = now;
                    phase_announced = false;
                }
                break;

            case DemoPhase::kSitDown:
                if (!phase_announced) {
                    std::cout << "send sit-down command, exit after 1 second" << std::endl;
                    phase_announced = true;
                }
                if (!motion_level_control.setSitDown()) {
                    std::cerr << "failed to send sit-down command" << std::endl;
                    return 1;
                }
                if (phase_elapsed >= std::chrono::seconds(5)) {
                    motion_level_control.disconnect();
                    return 0;
                }
                break;
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }

    return 0;
}
