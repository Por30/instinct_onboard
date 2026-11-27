#include <chrono>
#include <iostream>
#include <string>
#include <thread>

#include <unitree/robot/b2/motion_switcher/motion_switcher_client.hpp>
#include <unitree/robot/channel/channel_factory.hpp>

int main(int argc, char** argv) {
    const std::string action = argc == 2 ? argv[1] : "";
    if (action != "--status" && action != "--release") {
        std::cout << "Usage: factory-motion --status | --release\n";
        return action == "--help" ? 0 : 2;
    }

    unitree::robot::ChannelFactory::Instance()->Init(0, "enP8p1s0");
    unitree::robot::b2::MotionSwitcherClient client;
    client.SetTimeout(3.0F);
    client.Init();

    std::string form;
    std::string mode;
    auto status = client.CheckMode(form, mode);
    if (status != 0) {
        std::cerr << "CheckMode failed: " << status << '\n';
        return 1;
    }
    if (mode.empty()) {
        std::cout << "Factory motion: released\n";
        return 0;
    }
    std::cout << "Factory motion: " << mode << std::endl;
    if (action == "--status") {
        return 0;
    }

    status = client.ReleaseMode();
    if (status != 0) {
        std::cerr << "ReleaseMode failed: " << status << '\n';
        return 1;
    }
    for (int attempt = 0; attempt < 5; ++attempt) {
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
        status = client.CheckMode(form, mode);
        if (status != 0) {
            std::cerr << "CheckMode after ReleaseMode failed: " << status << '\n';
            return 1;
        }
        if (mode.empty()) {
            std::cout << "Factory motion: released\n";
            return 0;
        }
    }
    std::cerr << "Factory motion is still active: " << mode << '\n';
    return 1;
}
