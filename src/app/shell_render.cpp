// Taller de Colada - composition of the active native game frame.
// Copyright (C) 2026 BlackBearReloaded
// SPDX-License-Identifier: GPL-3.0-or-later

#include "app/shell.hpp"

#include "gfx/renderer.hpp"

namespace hui::app
{

void Shell::compose(gfx::Renderer &renderer)
{
    renderer.begin();
    if (concepts_.empty())
        return;
    frame_.reset();
    frame_.glass_texture = glass_texture_;
    concepts_[current_]->draw(frame_);
    renderer.backdrop(frame_.backdrop);
    renderer.draw(frame_.scene);
    if (frame_.glass)
        renderer.glass();
    renderer.draw(frame_.overlay);
    renderer.backdrop(frame_.post);

    // PS5HS_STANDALONE_RUNTIME_RENDER_V1: the game frame is the complete UI.
}

} // namespace hui::app
