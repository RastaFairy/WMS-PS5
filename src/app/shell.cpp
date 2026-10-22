// Taller de Colada - native application shell for its active game screen.
// Copyright (C) 2026 BlackBearReloaded
// SPDX-License-Identifier: GPL-3.0-or-later

#include "app/shell.hpp"

#include "core/save_file.hpp"
#include "platform/ps5/system.hpp"

#include <utility>

namespace hui::app
{

namespace
{

// PS5HS_STANDALONE_RUNTIME_ACTIONS_V1: controller actions belong to the game.

std::string settings_path(const std::string &data_root)
{
    return data_root + "/settings.bin";
}

} // namespace

Settings Shell::load_settings(const std::string &data_root)
{
    Settings settings;
    std::string data;
    if (save::read_file(settings_path(data_root), &data))
    {
        const save::Decoded decoded = save::decode(save::Kind::settings, data);
        if (!decoded.ok || !decode_settings(decoded.payload, &settings))
            sys::log("[HUI] settings unreadable (%s), using defaults", decoded.error.c_str());
    }
    return settings;
}

Shell::Shell(const ui::Fonts &fonts, const demo::Catalog &catalog, std::string data_root,
             std::uint32_t glass_texture)
    : fonts_(fonts), data_root_(std::move(data_root)), settings_(load_settings(data_root_)),
      context_{fonts_, catalog, telemetry_, settings_, data_root_}, glass_texture_(glass_texture)
{
    for (ConceptFactory factory : concept_registry())
        concepts_.push_back(factory(context_));
    if (!concepts_.empty())
    {
        current_ = static_cast<std::size_t>(settings_.concept_index) % concepts_.size();
        concepts_[current_]->enter();
    }
}

audio::SoundSet Shell::sound_set() const
{
    return concepts_.empty() ? audio::SoundSet::glass : concepts_[current_]->info().sounds;
}

gfx::Color Shell::accent() const
{
    return concepts_.empty() ? gfx::Color::rgb(0xffffff) : concepts_[current_]->info().accent;
}

bool Shell::take_settings_changed()
{
    const bool changed = settings_changed_;
    settings_changed_ = false;
    return changed;
}

void Shell::save_settings()
{
    const std::string error =
        save::write_atomic(settings_path(data_root_),
                           save::encode(save::Kind::settings, 1, encode_settings(settings_)));
    if (!error.empty())
        sys::log("[HUI] settings save failed: %s", error.c_str());
}

void Shell::update(const InputFrame &input, float dt)
{
    feedback_.clear();
    if (concepts_.empty())
        return;
    if (!welcomed_)
    {
        welcomed_ = true;
        feedback_.play(audio::Cue::welcome);
    }

    // PS5HS_STANDALONE_RUNTIME_UPDATE_V1: the game receives every button and axis unchanged.
    concepts_[current_]->update(input, dt, feedback_);

    if (context_.settings_changed)
    {
        context_.settings_changed = false;
        settings_changed_ = true;
        save_delay_ = 0.75f; // sliders change every frame: save once they rest
    }
    if (save_delay_ > 0.0f)
    {
        save_delay_ -= dt;
        if (save_delay_ <= 0.0f)
            save_settings();
    }

    telemetry_.uptime += static_cast<double>(dt);
}
// PS5HS_STANDALONE_RUNTIME_CHROME_V1: the game owns its complete presentation.

} // namespace hui::app
