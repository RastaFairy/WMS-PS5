// Taller de Colada - runtime shell for the single native game screen.
// Copyright (C) 2026 BlackBearReloaded
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include "app/concept.hpp"
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace hui::gfx
{
class Renderer;
}

namespace hui::app
{

// Owns the active native game screen, persists shared settings, and feeds
// telemetry to the game. Controller input belongs to the active screen.
class Shell
{
  public:
    Shell(const ui::Fonts &fonts, const demo::Catalog &catalog, std::string data_root,
          std::uint32_t glass_texture);

    static Settings load_settings(const std::string &data_root);

    void update(const InputFrame &input, float dt);
    // Queues this frame's layers; the caller presents them.
    void compose(gfx::Renderer &renderer);
    // Sounds and rumble requested during the last update.
    const Feedback &feedback() const
    {
        return feedback_;
    }
    audio::SoundSet sound_set() const;
    gfx::Color accent() const;

    const Settings &settings() const
    {
        return settings_;
    }
    // True once after the settings changed: apply volumes, button swap, ...
    bool take_settings_changed();

    Telemetry &telemetry()
    {
        return telemetry_;
    }
    // ---- for the native tour ----
    std::size_t concept_count() const
    {
        return concepts_.size();
    }
    const Concept &concept_at(std::size_t index) const
    {
        return *concepts_[index];
    }

  private:
    void save_settings();

    ui::Fonts fonts_;
    std::string data_root_;
    Settings settings_;
    Telemetry telemetry_;
    Context context_;
    std::vector<std::unique_ptr<Concept>> concepts_;
    std::size_t current_ = 0;
    Frame frame_;
    Feedback feedback_;
    std::uint32_t glass_texture_ = 0;
    bool settings_changed_ = true; // applied once at start-up
    float save_delay_ = 0.0f;      // > 0: a save is pending
    bool welcomed_ = false;
};

} // namespace hui::app
