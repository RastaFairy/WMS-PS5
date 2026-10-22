// Taller de Colada and Maestro Lavandero: native 2D game flow.
// Copyright (C) 2026 BlackBearReloaded
// SPDX-License-Identifier: GPL-3.0-or-later

#include "concepts/concepts.hpp"

#include "core/save_file.hpp"
#include "game/garment_sprites.hpp"
#include "game/laundry_game.hpp"
#include "platform/ps5/system.hpp"
#include "ui/feedback.hpp"
#include "ui/fonts.hpp"

#include <GL/glcorearb.h>

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdio>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace hui::concepts
{
namespace
{
using gfx::Color;
using gfx::Rect;
using game::Additive;
using game::Detergent;
using game::Evaluation;
using game::GarmentDefinition;
using game::LaundrySession;
using game::MachineSettings;
using game::Program;
using game::Softener;
using game::Treatment;

using GarmentAtlases = std::array<std::uint32_t, game::kGarmentAtlasCount>;

const Color kInk = Color::rgb(0x183247);
const Color kMuted = Color::rgb(0x718494);
const Color kAccent = Color::rgb(0x2a8eaa);
const Color kAccentDark = Color::rgb(0x155c78);
const Color kBackground = Color::rgb(0xf0f5f7);
const Color kPanel = Color::rgb(0xffffff);
const Color kSoftPanel = Color::rgb(0xeaf3f6);
const Color kBorder = Color::rgb(0xd8e3e8);
const Color kSelected = Color::rgb(0xe3f3f7);
const Color kGood = Color::rgb(0x2e815e);
const Color kWarn = Color::rgb(0xb56a18);
const Color kBad = Color::rgb(0xb14c45);

enum class Screen : std::uint8_t
{
    home,
    settings,
    levels,
    sorting,
    machine,
    label,
    treatment,
    manual,
    running,
    report,
    pause,
};

constexpr std::array<Program, 7> kPrograms = {
    Program::cotton, Program::synthetics, Program::delicates, Program::wool,
    Program::sport, Program::quick, Program::eco};
constexpr std::array<int, 5> kTemperatures = {20, 30, 40, 60, 90};
constexpr std::array<int, 5> kSpinSpeeds = {0, 400, 800, 1200, 1400};
constexpr std::array<Detergent, 6> kDetergents = {
    Detergent::none, Detergent::universal, Detergent::color, Detergent::wool,
    Detergent::sport, Detergent::eco};
constexpr std::array<Softener, 3> kSofteners = {
    Softener::none, Softener::standard, Softener::hypoallergenic};
constexpr std::array<Additive, 4> kAdditives = {
    Additive::none, Additive::oxygen_bleach, Additive::color_protect,
    Additive::chlorine_bleach};
constexpr std::array<Treatment, 5> kTreatments = {
    Treatment::none, Treatment::grease_remover, Treatment::cold_enzyme,
    Treatment::brush_prewash, Treatment::oxygen_spotter};

template <typename T, std::size_t N>
std::size_t option_index(const std::array<T, N> &options, T value, bool selected)
{
    if (!selected)
        return 0;
    const auto found = std::find(options.begin(), options.end(), value);
    return found == options.end() ? 0 : static_cast<std::size_t>(found - options.begin());
}

template <typename T, std::size_t N>
T rotate_choice(const std::array<T, N> &options, T current, bool selected, int direction)
{
    int index = static_cast<int>(option_index(options, current, selected));
    index = (index + direction + static_cast<int>(N)) % static_cast<int>(N);
    return options[static_cast<std::size_t>(index)];
}

std::string weight_text(int grams)
{
    char text[32]{};
    std::snprintf(text, sizeof(text), "%d.%03d kg", grams / 1000, std::abs(grams % 1000));
    return text;
}

bool load_garment_atlas(const char *path, std::uint32_t *texture)
{
    if (texture == nullptr)
        return false;
    *texture = 0;
    std::string bytes;
    constexpr std::size_t kHeaderBytes = 8;
    constexpr std::size_t kMaximumBytes = kHeaderBytes + 512u * 512u * 4u;
    if (!save::read_file(path, &bytes, kMaximumBytes) || bytes.size() < kHeaderBytes)
    {
        sys::log("[Laundry] garment atlas missing or unreadable: %s", path);
        return false;
    }
    const auto read_u32 = [&](std::size_t offset)
    {
        return static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[offset])) |
               (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[offset + 1])) << 8) |
               (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[offset + 2])) << 16) |
               (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[offset + 3])) << 24);
    };
    const std::uint32_t width = read_u32(0);
    const std::uint32_t height = read_u32(4);
    const std::uint64_t expected = kHeaderBytes +
        static_cast<std::uint64_t>(width) * height * 4u;
    if (width != 512 || height != 512 || expected != bytes.size())
    {
        sys::log("[Laundry] garment atlas has invalid RGBA dimensions: %s", path);
        return false;
    }

    // A previous renderer command may have left an unrelated GL error pending.
    // Clear it before this upload so the atlas result reflects these calls only.
    GLenum stale_error = GL_NO_ERROR;
    do
    {
        stale_error = glGetError();
    } while (stale_error != GL_NO_ERROR);
    GLuint handle = 0;
    glGenTextures(1, &handle);
    if (handle == 0)
    {
        sys::log("[Laundry] OpenGL could not allocate garment atlas: %s", path);
        return false;
    }
    glBindTexture(GL_TEXTURE_2D, handle);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, static_cast<GLsizei>(width),
                 static_cast<GLsizei>(height), 0, GL_RGBA, GL_UNSIGNED_BYTE,
                 reinterpret_cast<const unsigned char *>(bytes.data() + kHeaderBytes));
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 0);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    if (glGetError() != GL_NO_ERROR)
    {
        glDeleteTextures(1, &handle);
        sys::log("[Laundry] OpenGL rejected garment atlas: %s", path);
        return false;
    }
    *texture = handle;
    return true;
}

void load_garment_atlases(GarmentAtlases &textures)
{
    for (std::size_t i = 0; i < textures.size(); ++i)
    {
        char path[80]{};
        std::snprintf(path, sizeof(path),
                      "/app0/assets/garments/garment-atlas-%02u.rgba",
                      static_cast<unsigned>(i + 1));
        load_garment_atlas(path, &textures[i]);
    }
}

void draw_garment_image(gfx::DrawList &draw, std::string_view id, const Rect &bounds,
                        const GarmentAtlases &textures)
{
    const game::GarmentSprite *sprite = game::find_garment_sprite(id);
    if (sprite == nullptr || sprite->atlas >= textures.size() || textures[sprite->atlas] == 0)
        return;
    constexpr float kAtlasSize = 512.0f;
    constexpr float kSpriteSize = 128.0f;
    const Rect uv{static_cast<float>(sprite->x) / kAtlasSize,
                  static_cast<float>(sprite->y) / kAtlasSize,
                  kSpriteSize / kAtlasSize, kSpriteSize / kAtlasSize};
    draw.image(textures[sprite->atlas], bounds, uv, Color::rgb(0xffffff));
}

void draw_drum_water(gfx::DrawList &draw, float cx, float cy, float radius,
                     const game::CycleAnimation &animation, bool reduced_motion)
{
    const float level = std::clamp(animation.water_level, 0.0f, 0.62f);
    if (level <= 0.015f || radius <= 0.0f)
        return;

    constexpr float kPi = 3.14159265f;
    constexpr int kSurfaceSegments = 32;
    constexpr int kArcSegments = 48;
    constexpr int kVertexCount = kSurfaceSegments + 1 + kArcSegments - 1;
    std::array<float, static_cast<std::size_t>(kVertexCount) * 2> boundary{};
    const float surface_offset = radius * (1.0f - 2.0f * level);
    const float normalized_offset = std::clamp(surface_offset / radius, -1.0f, 1.0f);
    const float half_width = std::sqrt(std::max(0.0f,
        radius * radius - surface_offset * surface_offset));
    const float surface_y = cy + surface_offset;
    const float surface_angle = std::asin(normalized_offset);
    const float wave_amplitude = reduced_motion ? 0.0f : radius *
        (animation.phase == game::CyclePhase::rinsing ? 0.032f : 0.048f);
    int vertex = 0;
    for (int i = 0; i <= kSurfaceSegments; ++i)
    {
        const float u = static_cast<float>(i) / static_cast<float>(kSurfaceSegments);
        const float edge_taper = std::sin(kPi * u);
        const float wave = std::sin(animation.cycle_seconds * 3.1f + u * 2.0f * kPi) *
                           wave_amplitude * edge_taper;
        boundary[static_cast<std::size_t>(vertex) * 2] = cx + (2.0f * u - 1.0f) * half_width;
        boundary[static_cast<std::size_t>(vertex) * 2 + 1] = surface_y + wave;
        ++vertex;
    }
    for (int i = 1; i < kArcSegments; ++i)
    {
        const float u = static_cast<float>(i) / static_cast<float>(kArcSegments);
        const float angle = surface_angle + (kPi - 2.0f * surface_angle) * u;
        boundary[static_cast<std::size_t>(vertex) * 2] = cx + std::cos(angle) * radius;
        boundary[static_cast<std::size_t>(vertex) * 2 + 1] = cy + std::sin(angle) * radius;
        ++vertex;
    }
    draw.polygon(boundary.data(), vertex, Color::rgb(0x1689a4, 0.76f));

    for (int i = 0; i < kSurfaceSegments; ++i)
    {
        const std::size_t a = static_cast<std::size_t>(i) * 2;
        const std::size_t b = a + 2;
        draw.line(boundary[a], boundary[a + 1], boundary[b], boundary[b + 1],
                  std::max(1.0f, radius * 0.023f), Color::rgb(0xa6edf4, 0.76f));
    }

    if (animation.foam <= 0.02f)
        return;
    const float surface_clearance = radius * 0.07f;
    const float bubble_depth = std::max(0.0f, cy + radius - surface_y - surface_clearance);
    for (int bubble = 0; bubble < 8; ++bubble)
    {
        const float phase = (reduced_motion ? 0.0f : animation.cycle_seconds * 0.22f) +
                            static_cast<float>(bubble) * 0.137f;
        const float rise = 1.0f - (phase - std::floor(phase));
        const float by = surface_y + surface_clearance + rise * bubble_depth;
        const float dy = by - cy;
        const float horizontal_limit = std::sqrt(std::max(0.0f, radius * radius - dy * dy));
        const float sway = std::sin((reduced_motion ? 0.0f : animation.cycle_seconds * 1.35f) +
                                    static_cast<float>(bubble) * 1.9f);
        const float bx = cx + sway * horizontal_limit * 0.54f;
        const float alpha = animation.foam * (0.42f + 0.07f * static_cast<float>(bubble % 3));
        draw.circle(bx, by, radius * (0.024f + 0.006f * static_cast<float>(bubble % 3)),
                    Color::rgb(0xe9fbff, alpha));
    }
}

void draw_machine(gfx::DrawList &draw, const ui::Fonts &fonts, const Rect &bounds,
                  const game::LevelDefinition *level, const std::vector<game::ItemState> *items,
                  const game::CycleAnimation &animation, bool door_open,
                  const MachineSettings *settings, bool reduced_motion,
                  const GarmentAtlases &garment_atlases)
{
    const float s = std::min(bounds.w / 350.0f, bounds.h / 585.0f);
    const float x = bounds.x + (bounds.w - 350.0f * s) * 0.5f;
    const float y = bounds.y + (bounds.h - 585.0f * s) * 0.5f;
    draw.shadow(Rect{x + 18*s, y + 10*s, 314*s, 564*s}, 24*s, 18*s, Color::rgb(0x172b38, 0.16f));
    draw.bordered_rect(Rect{x + 18*s, y + 8*s, 314*s, 566*s}, 24*s, Color::rgb(0xe2e7e9),
                       2.0f*s, Color::rgb(0xb5c2c8));
    draw.rounded_rect(Rect{x + 28*s, y + 18*s, 294*s, 90*s}, 17*s, Color::rgb(0x182937));
    draw.rounded_rect(Rect{x + 43*s, y + 34*s, 100*s, 44*s}, 9*s, Color::rgb(0xdce8eb));
    hui::ui::text(draw, fonts.semibold, "NIVORA", x + 93*s, y + 62*s, 11*s, kAccentDark,
                  gfx::Align::center);
    draw.rounded_rect(Rect{x + 157*s, y + 31*s, 88*s, 52*s}, 9*s, Color::rgb(0x233d50));
    const char *display = settings != nullptr && settings->temperature_selected ? "LISTA" : "PREPARA";
    hui::ui::text(draw, fonts.semibold, display, x + 201*s, y + 53*s, 10*s,
                  Color::rgb(0xd9edf1), gfx::Align::center, 0.5f);
    if (settings != nullptr && settings->temperature_selected)
    {
        char temp[12]{};
        std::snprintf(temp, sizeof(temp), "%d C", settings->temperature_c);
        hui::ui::text(draw, fonts.mono, temp, x + 201*s, y + 72*s, 10*s,
                      Color::rgb(0x76d3e4), gfx::Align::center);
    }
    draw.circle(x + 282*s, y + 57*s, 16*s, Color::rgb(0xdce5e8));
    draw.circle(x + 282*s, y + 57*s, 11*s, kAccentDark);

    draw.rounded_rect(Rect{x + 34*s, y + 117*s, 282*s, 432*s}, 19*s, Color::rgb(0xbcc6ca));
    draw.rounded_rect(Rect{x + 48*s, y + 131*s, 254*s, 402*s}, 15*s, Color::rgb(0x26333d));
    const float cx = x + 175*s;
    const float cy = y + 330*s;
    const float r = 111*s;
    draw.circle(cx, cy, r + 16*s, Color::rgb(0x66757e));
    draw.circle(cx, cy, r + 8*s, Color::rgb(0xd9e0e3));
    draw.circle(cx, cy, r, Color::rgb(0x263e4d));
    draw.circle(cx, cy, r - 9*s, Color::rgb(0x172c3a));
    draw.circle(cx, cy, r - 17*s, Color::rgb(0x36586b));
    draw.circle(cx, cy, r - 22*s, Color::rgb(0x243d4b));

    draw_drum_water(draw, cx, cy, r - 27*s, animation, reduced_motion);

    if (level != nullptr && items != nullptr)
    {
        int visible = 0;
        for (std::size_t i = 0; i < items->size() && i < level->garments.size(); ++i)
        {
            if (!(*items)[i].loaded)
                continue;
            const int slot = visible++ % 6;
            const float angle = static_cast<float>(slot) * 1.04719755f +
                                (reduced_motion ? 0.0f : animation.drum_angle * 0.20f);
            const float orbit = 44*s + (reduced_motion ? 0.0f : animation.garment_sway * 16*s);
            const float gx = cx + std::cos(angle) * orbit;
            const float gy = cy + std::sin(angle) * orbit * 0.62f;
            draw_garment_image(draw, level->garments[i].id,
                               Rect{gx - 20*s, gy - 22*s, 40*s, 44*s}, garment_atlases);
        }
    }
    if (animation.foam > 0.02f)
    {
        draw.arc(cx, cy, r - 32*s, 2.0f*s, 4.15f, 0.34f,
                 Color::rgb(0xffffff, 0.14f), true);
    }
    draw.arc(cx, cy, r - 29*s, 2.6f*s, 4.55f, 0.46f,
             Color::rgb(0xffffff, 0.15f), true);
    draw.arc(cx, cy, r - 34*s, 1.5f*s, 5.35f, 0.28f,
             Color::rgb(0xffffff, 0.10f), true);
    draw.arc(cx, cy, r + 4*s, 8*s, 3.9f, 1.25f, Color::rgb(0xffffff, 0.34f), true);
    draw.arc(cx, cy, r + 4*s, 7*s, 0.75f, 0.5f, Color::rgb(0x263c49, 0.6f), true);
    if (door_open)
    {
        draw.rounded_rect(Rect{x + 283*s, y + 291*s, 36*s, 81*s}, 10*s,
                          Color::rgb(0x82919a, 0.8f));
        draw.circle(x + 301*s, y + 331*s, 10*s, Color::rgb(0xe7edef));
    }
    else
    {
        draw.rounded_rect(Rect{x + 300*s, y + 300*s, 14*s, 65*s}, 6*s,
                          Color::rgb(0x72818a));
    }
    hui::ui::text(draw, fonts.semibold, "TAMBOR", cx, y + 497*s, 10*s, Color::rgb(0xd6e8ec),
                  gfx::Align::center, 1.0f);
}

class TallerMenu final : public app::Concept
{
  public:
    explicit TallerMenu(app::Context &context)
        : context_(context), progress_(game::load_progress(context.save_root))
    {
        load_garment_atlases(garment_atlases_);
    }

    ~TallerMenu() override
    {
        for (std::uint32_t &texture : garment_atlases_)
        {
            if (texture != 0)
                glDeleteTextures(1, &texture);
            texture = 0;
        }
    }

    const app::ConceptInfo &info() const override
    {
        static const char *const kTechniques[] = {
            "Menú principal y ajustes nativos 2D", "Veinte niveles de clasificación y cuidado textil",
            "Peso de carga, lectura obligatoria de etiquetas, productos y ciclo animado",
            "Progreso por nivel guardado con contenedor verificado y escritura atómica"};
        static const app::ConceptInfo kInfo{
            "taller-menu", "Taller de Colada", "Menú y Maestro Lavandero",
            "src/concepts/taller_menu.cpp", audio::SoundSet::glass, kAccent, kTechniques};
        return kInfo;
    }

    void enter() override
    {
        if (screen_ == Screen::home)
            selected_home_ = 0;
    }

    void update(const InputFrame &input, float dt, app::Feedback &feedback) override
    {
        if (screen_ == Screen::running && input.is_pressed(Action::menu))
        {
            pause_return_ = Screen::running;
            selected_pause_ = 0;
            screen_ = Screen::pause;
            feedback.play(audio::Cue::modal_open);
            return;
        }
        if (screen_ == Screen::running)
        {
            if (input.is_pressed(Action::touch))
            {
                open_manual(Screen::running);
                feedback.play(audio::Cue::modal_open);
                return;
            }
            if (session_.advance_cycle(dt))
            {
                result_ = session_.evaluate();
                progress_.record(session_.level_index(), result_);
                if (!game::save_progress(context_.save_root, progress_))
                    status_ = "No se pudo guardar el progreso; los ajustes siguen disponibles.";
                else
                    status_ = "Progreso guardado.";
                selected_result_ = 0;
                screen_ = Screen::report;
                feedback.play(audio::Cue::complete, 1.0f, 0.0f, 0.85f);
                if (context_.settings.haptics)
                    feedback.rumble(0.55f, 0.12f);
            }
            return;
        }

        if (screen_ == Screen::label)
        {
            if (input.is_pressed(Action::back))
            {
                screen_ = return_screen_;
                feedback.play(audio::Cue::back);
            }
            else if (input.is_pressed(Action::confirm))
            {
                session_.mark_label_read(selected_garment_);
                screen_ = return_screen_;
                status_ = "Etiqueta leída. Ya puedes aplicar su cuidado al ciclo.";
                feedback.play(audio::Cue::select);
            }
            else if (input.is_pressed(Action::north))
            {
                open_manual(Screen::label);
                feedback.play(audio::Cue::modal_open);
            }
            return;
        }
        if (screen_ == Screen::treatment)
        {
            const GarmentDefinition &garment = session_.level().garments[selected_garment_];
            const std::size_t row_count = kTreatments.size() + (garment.needs_mesh ? 1u : 0u);
            if (input.nav == Direction::up || input.nav == Direction::left)
                selected_treatment_ = (selected_treatment_ + row_count - 1) % row_count;
            else if (input.nav == Direction::down || input.nav == Direction::right)
                selected_treatment_ = (selected_treatment_ + 1) % row_count;
            if (input.is_pressed(Action::back))
            {
                screen_ = Screen::sorting;
                feedback.play(audio::Cue::back);
            }
            else if (input.is_pressed(Action::confirm))
            {
                if (garment.needs_mesh && selected_treatment_ == kTreatments.size())
                {
                    const bool accepted = session_.toggle_mesh(selected_garment_);
                    const game::ItemState *item = session_.item_state(selected_garment_);
                    status_ = accepted && item != nullptr && item->in_mesh
                        ? "Bolsa de malla preparada para esta prenda."
                        : accepted ? "Prenda retirada de la bolsa de malla."
                                   : "Abre la puerta para cambiar la preparación.";
                    feedback.play(accepted ? audio::Cue::toggle : audio::Cue::error);
                    return;
                }
                const bool accepted = session_.choose_treatment(
                    selected_garment_, kTreatments[selected_treatment_]);
                status_ = accepted ? "Pretratamiento elegido para esta prenda."
                                   : "Abre la puerta y lee la etiqueta antes de preparar la prenda.";
                screen_ = Screen::sorting;
                feedback.play(accepted ? audio::Cue::select : audio::Cue::error);
            }
            return;
        }
        if (screen_ == Screen::manual)
        {
            if (input.is_pressed(Action::back) || input.is_pressed(Action::confirm) ||
                input.is_pressed(Action::touch))
            {
                screen_ = return_screen_;
                feedback.play(audio::Cue::back);
            }
            return;
        }
        if (screen_ == Screen::pause)
        {
            update_pause(input, feedback);
            return;
        }

        if (input.is_pressed(Action::menu) &&
            (screen_ == Screen::sorting || screen_ == Screen::machine))
        {
            pause_return_ = screen_;
            selected_pause_ = 0;
            screen_ = Screen::pause;
            feedback.play(audio::Cue::modal_open);
            return;
        }

        switch (screen_)
        {
        case Screen::home:
            update_home(input, feedback);
            break;
        case Screen::settings:
            update_settings(input, feedback);
            break;
        case Screen::levels:
            update_levels(input, feedback);
            break;
        case Screen::sorting:
            update_sorting(input, feedback);
            break;
        case Screen::machine:
            update_machine(input, feedback);
            break;
        case Screen::report:
            update_report(input, feedback);
            break;
        case Screen::label:
        case Screen::treatment:
        case Screen::manual:
        case Screen::running:
        case Screen::pause:
            break;
        }
    }

    void draw(app::Frame &frame) const override
    {
        frame.backdrop.mode = gfx::BackdropMode::gradient;
        frame.backdrop.colors[0] = kBackground;
        frame.backdrop.colors[1] = Color::rgb(0xe4eef2);
        frame.backdrop.colors[2] = Color::rgb(0xf8fafb);
        frame.backdrop.params[0] = 0.16f;
        frame.backdrop.params[1] = 0.08f;
        frame.backdrop.params[2] = 0.42f;
        draw_common(frame.scene);
        switch (screen_)
        {
        case Screen::home: draw_home(frame.scene); break;
        case Screen::settings: draw_settings(frame.scene); break;
        case Screen::levels: draw_levels(frame.scene); break;
        case Screen::sorting: draw_sorting(frame.scene); break;
        case Screen::machine: draw_machine_setup(frame.scene); break;
        case Screen::running: draw_cycle(frame.scene); break;
        case Screen::report: draw_report(frame.scene); break;
        case Screen::label:
            draw_return_screen(frame.scene);
            draw_label(frame.overlay);
            break;
        case Screen::treatment:
            draw_sorting(frame.scene);
            draw_treatment(frame.overlay);
            break;
        case Screen::manual:
            draw_return_screen(frame.scene);
            draw_manual(frame.overlay);
            break;
        case Screen::pause:
            draw_return_screen(frame.scene);
            draw_pause(frame.overlay);
            break;
        }
    }

  private:
    void draw_common(gfx::DrawList &draw) const
    {
        draw.circle(110.0f, 145.0f, 128.0f, Color::rgb(0xdbecef, 0.44f));
        draw.circle(1805.0f, 895.0f, 165.0f, Color::rgb(0xe0edf1, 0.4f));
        const Rect shell{54.0f, 42.0f, 1812.0f, 990.0f};
        draw.shadow(shell, 32.0f, 27.0f, Color::rgb(0x274a5b, 0.10f));
        draw.bordered_rect(shell, 32.0f, kPanel, 2.0f, kBorder);
        draw.rounded_rect(Rect{85, 72, 54, 54}, 16, kAccent);
        draw.circle(112, 99, 18, Color::rgb(0xffffff));
        draw.circle(112, 99, 12, kAccentDark);
        draw.circle(112, 99, 6, Color::rgb(0xc8e8ee));
        hui::ui::text(draw, context_.fonts.display, "TALLER DE COLADA", 158, 103, 27, kInk);
        hui::ui::text(draw, context_.fonts.regular, "MAESTRO LAVANDERO 2D", 160, 128, 12,
                      kMuted, gfx::Align::left, 1.2f);
        char progress[64]{};
        std::snprintf(progress, sizeof(progress), "PROGRESO  %02d / %02d",
                      static_cast<int>(std::popcount(progress_.completed_mask)),
                      static_cast<int>(game::kLevelCount));
        hui::ui::text(draw, context_.fonts.semibold, progress, 1785, 103, 13, kAccentDark,
                      gfx::Align::right, 1.0f);
        hui::ui::text(draw, context_.fonts.regular, "Puntuación récord", 1785, 128, 12, kMuted,
                      gfx::Align::right);
        char score[32]{};
        std::snprintf(score, sizeof(score), "%d", progress_.total_best_score());
        hui::ui::text(draw, context_.fonts.mono, score, 1785, 153, 16, kInk,
                      gfx::Align::right);
        draw.line(86, 166, 1834, 166, 1.0f, kBorder);
    }

    void draw_footer(gfx::DrawList &draw, std::string_view text) const
    {
        draw.rounded_rect(Rect{82, 967, 1756, 44}, 14, Color::rgb(0xf1f6f8));
        std::string controls(text);
        if (context_.settings.swap_confirm)
        {
            for (std::size_t i = 0; i < controls.size(); ++i)
            {
                const char next = i + 1 < controls.size() ? controls[i + 1] : '\0';
                const bool token = next == ':' || next == '\0' ||
                                   (next == ' ' && i + 2 < controls.size() && controls[i + 2] == '/');
                if (token && controls[i] == 'X') controls[i] = '\x01';
                else if (token && controls[i] == 'O') controls[i] = 'X';
            }
            std::replace(controls.begin(), controls.end(), '\x01', 'O');
        }
        hui::ui::text(draw, context_.fonts.semibold, controls, 960, 995, 13, kMuted,
                      gfx::Align::center, 0.2f);
    }

    void update_home(const InputFrame &input, app::Feedback &feedback)
    {
        if (input.nav == Direction::up || input.nav == Direction::down)
        {
            const int direction = input.nav == Direction::up ? -1 : 1;
            selected_home_ = (selected_home_ + direction + 3) % 3;
            feedback.play(audio::Cue::focus, 1.0f, 0.0f, 0.55f);
        }
        if (input.is_pressed(Action::confirm))
        {
            if (selected_home_ == 0)
            {
                selected_level_ = progress_.unlocked_through;
                screen_ = Screen::levels;
            }
            else if (selected_home_ == 1)
            {
                selected_setting_ = 0;
                screen_ = Screen::settings;
            }
            else
                hui::sys::quit();
            feedback.play(audio::Cue::select);
        }
    }

    void update_settings(const InputFrame &input, app::Feedback &feedback)
    {
        if (input.nav == Direction::up || input.nav == Direction::down)
        {
            const int direction = input.nav == Direction::up ? -1 : 1;
            selected_setting_ = (selected_setting_ + direction + 5) % 5;
            feedback.play(audio::Cue::focus, 1.0f, 0.0f, 0.5f);
        }
        const int direction = input.nav == Direction::left ? -1 :
                              input.nav == Direction::right ? 1 : 0;
        if (direction != 0)
            change_setting(direction, feedback);
        if (input.is_pressed(Action::confirm))
        {
            if (selected_setting_ == 4)
            {
                screen_ = Screen::home;
                feedback.play(audio::Cue::back);
            }
            else if (selected_setting_ != 0)
                change_setting(1, feedback);
        }
        if (input.is_pressed(Action::back))
        {
            screen_ = Screen::home;
            feedback.play(audio::Cue::back);
        }
    }

    void change_setting(int direction, app::Feedback &feedback)
    {
        auto &settings = context_.settings;
        bool changed = false;
        switch (selected_setting_)
        {
        case 0:
        {
            const int next = std::clamp(settings.ui_volume + direction, 0, 10);
            changed = next != settings.ui_volume;
            settings.ui_volume = next;
            if (changed)
                feedback.play(audio::Cue::slider, 1.0f, 0.0f, 0.6f);
            break;
        }
        case 1: settings.reduced_motion = !settings.reduced_motion; changed = true; break;
        case 2: settings.haptics = !settings.haptics; changed = true; break;
        case 3: settings.swap_confirm = !settings.swap_confirm; changed = true; break;
        default: break;
        }
        if (changed)
        {
            context_.settings_changed = true;
            if (selected_setting_ != 0)
            {
                feedback.play(audio::Cue::toggle, 1.0f, 0.0f, 0.65f);
                if (settings.haptics)
                    feedback.rumble(0.11f, 0.045f);
            }
        }
    }

    void update_levels(const InputFrame &input, app::Feedback &feedback)
    {
        int next = static_cast<int>(selected_level_);
        switch (input.nav)
        {
        case Direction::up: next -= 4; break;
        case Direction::down: next += 4; break;
        case Direction::left: --next; break;
        case Direction::right: ++next; break;
        case Direction::none: break;
        }
        selected_level_ = static_cast<std::size_t>(std::clamp(next, 0,
            static_cast<int>(game::kLevelCount) - 1));
        const int page_step = input.is_pressed(Action::page_prev) ? -4 :
                              input.is_pressed(Action::page_next) ? 4 : 0;
        if (page_step != 0)
        {
            selected_level_ = static_cast<std::size_t>(std::clamp(
                static_cast<int>(selected_level_) + page_step, 0,
                static_cast<int>(game::kLevelCount) - 1));
            feedback.play(audio::Cue::focus, 1.0f, 0.0f, 0.45f);
        }
        if (input.nav != Direction::none)
            feedback.play(audio::Cue::focus, 1.0f, 0.0f, 0.45f);
        if (input.is_pressed(Action::back))
        {
            screen_ = Screen::home;
            feedback.play(audio::Cue::back);
        }
        else if (input.is_pressed(Action::confirm))
        {
            if (selected_level_ > progress_.unlocked_through)
            {
                status_ = "Completa el nivel anterior para desbloquear esta misión.";
                feedback.play(audio::Cue::error);
                return;
            }
            begin_level(selected_level_);
            feedback.play(audio::Cue::select);
        }
    }

    void update_sorting(const InputFrame &input, app::Feedback &feedback)
    {
        const std::size_t count = session_.level().garments.size();
        int next = static_cast<int>(selected_garment_);
        switch (input.nav)
        {
        case Direction::up: next -= 2; break;
        case Direction::down: next += 2; break;
        case Direction::left: --next; break;
        case Direction::right: ++next; break;
        case Direction::none: break;
        }
        selected_garment_ = static_cast<std::size_t>(std::clamp(next, 0,
            std::max(0, static_cast<int>(count) - 1)));
        const int garment_step = input.is_pressed(Action::page_prev) ? -1 :
                                 input.is_pressed(Action::page_next) ? 1 : 0;
        if (garment_step != 0)
        {
            selected_garment_ = static_cast<std::size_t>(std::clamp(
                static_cast<int>(selected_garment_) + garment_step, 0,
                std::max(0, static_cast<int>(count) - 1)));
            feedback.play(audio::Cue::focus, 1.0f, 0.0f, 0.45f);
        }
        if (input.nav != Direction::none)
            feedback.play(audio::Cue::focus, 1.0f, 0.0f, 0.45f);

        if (input.is_pressed(Action::touch))
        {
            open_label(Screen::sorting);
            feedback.play(audio::Cue::modal_open);
            return;
        }

        if (input.is_pressed(Action::l3))
        {
            session_.set_door_open(!session_.door_open());
            status_ = session_.door_open() ? "Puerta abierta." : "Puerta cerrada.";
            feedback.play(audio::Cue::toggle);
            return;
        }
        if (input.is_pressed(Action::r3))
        {
            open_label(Screen::sorting);
            feedback.play(audio::Cue::modal_open);
            return;
        }
        if (input.is_pressed(Action::west))
        {
            const GarmentDefinition &garment = session_.level().garments[selected_garment_];
            const game::ItemState *state = session_.item_state(selected_garment_);
            if (state == nullptr)
            {
                status_ = "No se encontró la prenda seleccionada.";
                feedback.play(audio::Cue::error);
                return;
            }
            if (!state->label_read)
            {
                open_label(Screen::sorting);
                status_ = "Lee primero la etiqueta para preparar su cuidado.";
                feedback.play(audio::Cue::modal_open);
                return;
            }
            if (state->loaded)
            {
                status_ = "Abre la puerta y retira la prenda antes de cambiar su preparación.";
                feedback.play(audio::Cue::error);
                return;
            }
            if (garment.stain != game::Stain::none)
            {
                const auto found = std::find(kTreatments.begin(), kTreatments.end(), state->treatment);
                selected_treatment_ = found == kTreatments.end()
                    ? 0 : static_cast<std::size_t>(found - kTreatments.begin());
                screen_ = Screen::treatment;
                feedback.play(audio::Cue::modal_open);
                return;
            }
            if (session_.toggle_mesh(selected_garment_))
            {
                status_ = session_.item_state(selected_garment_)->in_mesh
                              ? "Bolsa de malla preparada para esta prenda."
                              : "Prenda retirada de la bolsa de malla.";
                feedback.play(audio::Cue::toggle);
                return;
            }
            status_ = garment.needs_mesh
                ? "Abre la puerta y lee la etiqueta antes de preparar la bolsa de malla."
                : "Esta prenda no necesita tratamiento ni bolsa de malla.";
            feedback.play(audio::Cue::error);
            return;
        }
        if (input.is_pressed(Action::north))
        {
            open_manual(Screen::sorting);
            feedback.play(audio::Cue::modal_open);
            return;
        }
        if (input.is_pressed(Action::jump_next))
        {
            control_index_ = 0;
            screen_ = Screen::machine;
            feedback.play(audio::Cue::tab);
            return;
        }
        if (input.is_pressed(Action::back))
        {
            pause_return_ = Screen::sorting;
            selected_pause_ = 0;
            screen_ = Screen::pause;
            feedback.play(audio::Cue::modal_open);
            return;
        }
        if (input.is_pressed(Action::confirm))
        {
            const game::MoveResult moved = session_.move_item(selected_garment_);
            switch (moved)
            {
            case game::MoveResult::loaded:
                status_ = "Prenda cargada.";
                feedback.play(audio::Cue::select);
                if (context_.settings.haptics)
                    feedback.rumble(0.08f, 0.04f);
                break;
            case game::MoveResult::unloaded:
                status_ = "Prenda devuelta a la cesta.";
                feedback.play(audio::Cue::back);
                break;
            case game::MoveResult::label_not_read:
                open_label(Screen::sorting);
                status_ = "Lee la etiqueta antes de cargar esta prenda.";
                feedback.play(audio::Cue::modal_open);
                break;
            case game::MoveResult::door_closed:
                status_ = "Abre la puerta con L3 antes de mover prendas.";
                feedback.play(audio::Cue::error);
                break;
            case game::MoveResult::capacity_exceeded:
                status_ = "No cabe: prendas y 2 kg de agua superarían los 8 kg.";
                feedback.play(audio::Cue::error);
                if (context_.settings.haptics)
                    feedback.rumble(0.20f, 0.08f);
                break;
            case game::MoveResult::invalid_item:
                status_ = "No se encontró la prenda seleccionada.";
                feedback.play(audio::Cue::error);
                break;
            }
        }
    }

    void update_machine(const InputFrame &input, app::Feedback &feedback)
    {
        if (input.nav == Direction::up || input.nav == Direction::down)
        {
            const int direction = input.nav == Direction::up ? -1 : 1;
            control_index_ = (control_index_ + direction + 8) % 8;
            feedback.play(audio::Cue::focus, 1.0f, 0.0f, 0.45f);
        }
        const int setting_step = input.is_pressed(Action::page_prev) ? -1 :
                                 input.is_pressed(Action::page_next) ? 1 : 0;
        if (setting_step != 0)
        {
            control_index_ = (control_index_ + setting_step + 8) % 8;
            feedback.play(audio::Cue::focus, 1.0f, 0.0f, 0.45f);
        }
        if (input.nav == Direction::left || input.nav == Direction::right)
        {
            if (control_index_ == 0)
                toggle_door(feedback);
            else if (control_index_ < 7)
                cycle_control(input.nav == Direction::left ? -1 : 1, feedback);
        }
        if (input.is_pressed(Action::jump_next))
        {
            control_index_ = 7;
            feedback.play(audio::Cue::focus, 1.0f, 0.0f, 0.45f);
        }
        if (input.is_pressed(Action::jump_prev))
        {
            screen_ = Screen::sorting;
            feedback.play(audio::Cue::tab, 1.0f, -0.2f);
            return;
        }
        if (input.is_pressed(Action::back))
        {
            pause_return_ = Screen::machine;
            selected_pause_ = 0;
            screen_ = Screen::pause;
            feedback.play(audio::Cue::modal_open);
            return;
        }
        if (input.is_pressed(Action::north))
        {
            open_manual(Screen::machine);
            feedback.play(audio::Cue::modal_open);
            return;
        }
        if (input.is_pressed(Action::touch))
        {
            open_manual(Screen::machine);
            feedback.play(audio::Cue::modal_open);
            return;
        }
        if (input.is_pressed(Action::r3))
        {
            open_label(Screen::machine);
            feedback.play(audio::Cue::modal_open);
            return;
        }
        if (input.is_pressed(Action::confirm))
        {
            if (control_index_ == 0)
            {
                toggle_door(feedback);
                return;
            }
            if (control_index_ == 7)
            {
                request_start_cycle(feedback);
                return;
            }
            if (control_is_selected(control_index_))
                cycle_control(1, feedback);
            else
                select_current_control(feedback);
        }
    }

    void update_report(const InputFrame &input, app::Feedback &feedback)
    {
        const bool has_next = session_.level_index() + 1 < game::kLevelCount;
        const int max_choice = has_next ? 3 : 2;
        if (input.nav == Direction::up || input.nav == Direction::left)
            selected_result_ = (selected_result_ + max_choice) % (max_choice + 1);
        else if (input.nav == Direction::down || input.nav == Direction::right)
            selected_result_ = (selected_result_ + 1) % (max_choice + 1);
        if (input.is_pressed(Action::confirm))
        {
            if (has_next)
            {
                if (selected_result_ == 0) begin_level(session_.level_index() + 1);
                else if (selected_result_ == 1) begin_level(session_.level_index());
                else if (selected_result_ == 2) screen_ = Screen::levels;
                else screen_ = Screen::home;
            }
            else
            {
                if (selected_result_ == 0) begin_level(session_.level_index());
                else if (selected_result_ == 1) screen_ = Screen::levels;
                else screen_ = Screen::home;
            }
            feedback.play(audio::Cue::select);
        }
        if (input.is_pressed(Action::back))
        {
            screen_ = Screen::levels;
            feedback.play(audio::Cue::back);
        }
    }

    void update_pause(const InputFrame &input, app::Feedback &feedback)
    {
        if (input.nav == Direction::up || input.nav == Direction::left)
            selected_pause_ = (selected_pause_ + 3) % 4;
        else if (input.nav == Direction::down || input.nav == Direction::right)
            selected_pause_ = (selected_pause_ + 1) % 4;
        if (input.is_pressed(Action::back) || input.is_pressed(Action::menu))
        {
            screen_ = pause_return_;
            feedback.play(audio::Cue::back);
        }
        else if (input.is_pressed(Action::confirm))
        {
            switch (selected_pause_)
            {
            case 0: screen_ = pause_return_; break;
            case 1: begin_level(session_.level_index()); break;
            case 2: screen_ = Screen::levels; break;
            case 3: screen_ = Screen::home; break;
            }
                feedback.play(audio::Cue::select);
        }
    }

    void begin_level(std::size_t index)
    {
        session_.begin_level(index);
        selected_level_ = session_.level_index();
        selected_garment_ = 0;
        control_index_ = 0;
        selected_treatment_ = 0;
        result_ = {};
        status_.clear();
        screen_ = Screen::sorting;
    }

    void toggle_door(app::Feedback &feedback)
    {
        session_.set_door_open(!session_.door_open());
        status_ = session_.door_open() ? "Puerta abierta." : "Puerta cerrada.";
        feedback.play(audio::Cue::toggle);
    }

    void request_start_cycle(app::Feedback &feedback)
    {
        const game::StartBlock block = session_.start_block();
        if (block != game::StartBlock::none)
        {
            status_ = game::start_block_message(block);
            feedback.play(audio::Cue::error);
            if (context_.settings.haptics)
                feedback.rumble(0.17f, 0.07f);
            return;
        }
        if (!session_.start_cycle())
        {
            const game::StartBlock latest_block = session_.start_block();
            status_ = latest_block == game::StartBlock::none
                ? "No se pudo iniciar el ciclo. Vuelve a revisar la preparación."
                : game::start_block_message(latest_block);
            feedback.play(audio::Cue::error);
            if (context_.settings.haptics)
                feedback.rumble(0.17f, 0.07f);
            return;
        }

        status_ = "El ciclo ha comenzado.";
        screen_ = Screen::running;
        feedback.play(audio::Cue::select);
        if (context_.settings.haptics)
            feedback.rumble(0.24f, 0.08f);
    }

    template <typename T, std::size_t N>
    void set_choice(const std::array<T, N> &options, T *value, bool *selected, int direction,
                    app::Feedback &feedback)
    {
        *value = rotate_choice(options, *value, *selected, direction);
        *selected = true;
        status_ = "Ajuste seleccionado.";
        feedback.play(audio::Cue::slider, 1.0f, 0.0f, 0.5f);
    }

    void cycle_control(int direction, app::Feedback &feedback)
    {
        MachineSettings &machine = session_.machine_settings();
        switch (control_index_)
        {
        case 1:
            set_choice(kPrograms, &machine.program, &machine.program_selected, direction, feedback);
            break;
        case 2:
        {
            std::size_t index = 0;
            if (machine.temperature_selected)
            {
                const auto found = std::find(kTemperatures.begin(), kTemperatures.end(), machine.temperature_c);
                if (found != kTemperatures.end()) index = static_cast<std::size_t>(found - kTemperatures.begin());
            }
            index = static_cast<std::size_t>((static_cast<int>(index) + direction +
                     static_cast<int>(kTemperatures.size())) % static_cast<int>(kTemperatures.size()));
            machine.temperature_c = kTemperatures[index];
            machine.temperature_selected = true;
            status_ = "Temperatura seleccionada.";
            feedback.play(audio::Cue::slider);
            break;
        }
        case 3:
        {
            std::size_t index = 0;
            if (machine.spin_selected)
            {
                const auto found = std::find(kSpinSpeeds.begin(), kSpinSpeeds.end(), machine.spin_rpm);
                if (found != kSpinSpeeds.end()) index = static_cast<std::size_t>(found - kSpinSpeeds.begin());
            }
            index = static_cast<std::size_t>((static_cast<int>(index) + direction +
                     static_cast<int>(kSpinSpeeds.size())) % static_cast<int>(kSpinSpeeds.size()));
            machine.spin_rpm = kSpinSpeeds[index];
            machine.spin_selected = true;
            status_ = "Velocidad seleccionada.";
            feedback.play(audio::Cue::slider);
            break;
        }
        case 4:
            set_choice(kDetergents, &machine.detergent, &machine.detergent_selected, direction, feedback);
            break;
        case 5:
            set_choice(kSofteners, &machine.softener, &machine.softener_selected, direction, feedback);
            break;
        case 6:
            set_choice(kAdditives, &machine.additive, &machine.additive_selected, direction, feedback);
            break;
        default:
            break;
        }
    }

    void select_current_control(app::Feedback &feedback)
    {
        MachineSettings &machine = session_.machine_settings();
        switch (control_index_)
        {
        case 1: machine.program = kPrograms[0]; machine.program_selected = true; break;
        case 2: machine.temperature_c = kTemperatures[0]; machine.temperature_selected = true; break;
        case 3: machine.spin_rpm = kSpinSpeeds[0]; machine.spin_selected = true; break;
        case 4: machine.detergent = kDetergents[0]; machine.detergent_selected = true; break;
        case 5: machine.softener = kSofteners[0]; machine.softener_selected = true; break;
        case 6: machine.additive = kAdditives[0]; machine.additive_selected = true; break;
        default: break;
        }
        status_ = "Ajuste seleccionado.";
        feedback.play(audio::Cue::select);
    }

    bool control_is_selected(int index) const
    {
        const MachineSettings &machine = session_.machine_settings();
        switch (index)
        {
        case 1: return machine.program_selected;
        case 2: return machine.temperature_selected;
        case 3: return machine.spin_selected;
        case 4: return machine.detergent_selected;
        case 5: return machine.softener_selected;
        case 6: return machine.additive_selected;
        default: return false;
        }
    }

    void open_label(Screen return_to)
    {
        return_screen_ = return_to;
        screen_ = Screen::label;
    }

    void open_manual(Screen return_to)
    {
        return_screen_ = return_to;
        screen_ = Screen::manual;
    }

    void draw_home(gfx::DrawList &draw) const
    {
        draw.bordered_rect(Rect{88, 194, 1744, 708}, 28, Color::rgb(0xf9fbfc), 1.5f, kBorder);
        draw.rounded_rect(Rect{132, 232, 604, 626}, 24, kSoftPanel);
        game::CycleAnimation idle;
        draw_machine(draw, context_.fonts, Rect{270, 274, 330, 540}, nullptr, nullptr, idle,
                     false, nullptr, context_.settings.reduced_motion, garment_atlases_);
        hui::ui::text(draw, context_.fonts.semibold, "SIMULADOR EDUCATIVO", 168, 786, 15,
                      kAccentDark, gfx::Align::left, 1.4f);
        hui::ui::paragraph(draw, context_.fonts.regular,
            "Lee las etiquetas, clasifica las prendas y prepara cada colada con criterio.",
            168, 819, 18, 500, 25, kMuted, 3);

        hui::ui::text(draw, context_.fonts.semibold, "MAESTRO LAVANDERO", 812, 275, 15,
                      kAccentDark, gfx::Align::left, 2.0f);
        hui::ui::text(draw, context_.fonts.display, "Prepara la colada", 812, 332, 38, kInk);
        hui::ui::paragraph(draw, context_.fonts.regular,
            "Veinte retos progresivos de tejidos, programas, productos y cuidado de las prendas.",
            812, 371, 19, 800, 27, kMuted, 3);
        const char *labels[] = {"Jugar / continuar", "Opciones", "Cerrar aplicación"};
        for (std::size_t i = 0; i < 3U; ++i)
        {
            const Rect row{812, 468.0f + static_cast<float>(i) * 102.0f, 890, 78};
            const bool selected = selected_home_ == i;
            draw.bordered_rect(row, 16, selected ? kSelected : Color::rgb(0xffffff),
                               selected ? 2.0f : 1.0f, selected ? kAccent : kBorder);
            if (selected)
                draw.rounded_rect(Rect{row.x + 14, row.y + 16, 5, 46}, 2.5f, kAccent);
            char index[8]{};
            std::snprintf(index, sizeof(index), "%02d", static_cast<int>(i + 1U));
            hui::ui::text(draw, context_.fonts.mono, index, row.x + 40, row.y + 48, 14,
                          selected ? kAccentDark : kMuted);
            hui::ui::text(draw, context_.fonts.semibold, labels[i], row.x + 88, row.y + 49,
                          20, kInk);
            if (i == 0)
            {
                char value[36]{};
                std::snprintf(value, sizeof(value), "NIVEL %02d",
                              static_cast<int>(progress_.unlocked_through) + 1);
                hui::ui::text(draw, context_.fonts.semibold, value, row.x + row.w - 24,
                              row.y + 48, 13, kAccentDark, gfx::Align::right, 1.0f);
            }
        }
        draw_footer(draw, "Flechas / stick: navegar     X: seleccionar");
    }

    void draw_settings(gfx::DrawList &draw) const
    {
        draw.bordered_rect(Rect{88, 194, 1744, 708}, 28, Color::rgb(0xf9fbfc), 1.5f, kBorder);
        hui::ui::text(draw, context_.fonts.semibold, "OPCIONES", 148, 250, 15, kAccentDark,
                      gfx::Align::left, 2.0f);
        hui::ui::text(draw, context_.fonts.display, "Ajustes del sistema", 148, 302, 34, kInk);
        const char *labels[] = {"Volumen de interfaz", "Reducir movimiento", "Vibración",
                                "Botón de confirmar", "Volver al menú"};
        for (std::size_t i = 0; i < 5U; ++i)
        {
            const float y = 350.0f + static_cast<float>(i) * 96.0f;
            const bool selected = selected_setting_ == i;
            draw.bordered_rect(Rect{148, y, 1624, 76}, 15,
                selected ? kSelected : Color::rgb(0xffffff), selected ? 2.0f : 1.0f,
                selected ? kAccent : kBorder);
            hui::ui::text(draw, context_.fonts.semibold, labels[i], 190, y + 47, 19, kInk);
            char value[48]{};
            Color value_color = kAccentDark;
            if (i == 0)
                std::snprintf(value, sizeof(value), "%02d / 10", context_.settings.ui_volume);
            else if (i == 1)
                std::snprintf(value, sizeof(value), "%s", context_.settings.reduced_motion ? "SÍ" : "NO");
            else if (i == 2)
                std::snprintf(value, sizeof(value), "%s", context_.settings.haptics ? "SÍ" : "NO");
            else if (i == 3)
                std::snprintf(value, sizeof(value), "%s", context_.settings.swap_confirm ? "CÍRCULO" : "CRUZ");
            else
                std::snprintf(value, sizeof(value), "VOLVER");
            if (i == 2 && !context_.settings.haptics) value_color = kMuted;
            hui::ui::text(draw, context_.fonts.semibold, value, 1728, y + 47, 16, value_color,
                          gfx::Align::right);
            if (i == 0)
            {
                for (int tick = 0; tick < 10; ++tick)
                    draw.rounded_rect(Rect{1460.0f + tick*18.0f, y + 59, 12, 5}, 2,
                        tick < context_.settings.ui_volume ? kAccent : Color::rgb(0xd4e1e7));
            }
        }
        draw_footer(draw, "Flechas: cambiar     X: activar / volver     O: cerrar opciones");
    }

    void draw_levels(gfx::DrawList &draw) const
    {
        draw.bordered_rect(Rect{88, 194, 1744, 708}, 28, Color::rgb(0xf9fbfc), 1.5f, kBorder);
        hui::ui::text(draw, context_.fonts.semibold, "MAPA DE MISIONES", 132, 242, 14,
                      kAccentDark, gfx::Align::left, 1.8f);
        hui::ui::text(draw, context_.fonts.display, "Elige un nivel", 132, 286, 30, kInk);
        const auto levels = game::level_catalog();
        for (std::size_t i = 0; i < levels.size(); ++i)
        {
            const int col = static_cast<int>(i % 4);
            const int row = static_cast<int>(i / 4);
            const Rect card{125.0f + col*425.0f, 328.0f + row*108.0f, 392.0f, 92.0f};
            const bool open = i <= progress_.unlocked_through;
            const bool selected = i == selected_level_;
            draw.bordered_rect(card, 14,
                selected ? kSelected : open ? Color::rgb(0xffffff) : Color::rgb(0xf1f3f4),
                selected ? 2.0f : 1.0f, selected ? kAccent : kBorder);
            char number[20]{};
            std::snprintf(number, sizeof(number), "NIVEL %02d", levels[i].number);
            hui::ui::text(draw, context_.fonts.semibold, number, card.x + 18, card.y + 28,
                          12, open ? kAccentDark : kMuted, gfx::Align::left, 1.1f);
            hui::ui::paragraph(draw, context_.fonts.semibold, levels[i].title, card.x + 18,
                               card.y + 53, 14, card.w - 36, 18,
                               open ? kInk : kMuted, 1);
            if (!open)
                hui::ui::text(draw, context_.fonts.regular, "CERRADO", card.x + card.w - 15,
                              card.y + 27, 10, kMuted, gfx::Align::right, 0.7f);
            else if ((progress_.completed_mask & (1u << i)) != 0)
            {
                char stars[12]{};
                const int star_count = progress_.best_stars[i];
                std::snprintf(stars, sizeof(stars), "%d / 3", star_count);
                hui::ui::text(draw, context_.fonts.semibold, stars, card.x + card.w - 15,
                              card.y + 27, 10, Color::rgb(0xb4801d), gfx::Align::right);
            }
        }
        draw_footer(draw, "Flechas / stick: recorrer niveles     L1/R1: fila anterior/siguiente     X: iniciar     O: volver");
    }

    void draw_sorting(gfx::DrawList &draw) const
    {
        const auto &level = session_.level();
        draw.bordered_rect(Rect{82, 188, 1756, 746}, 26, Color::rgb(0xf9fbfc), 1.5f, kBorder);
        hui::ui::text(draw, context_.fonts.semibold, "CLASIFICACIÓN Y ETIQUETAS", 118, 225,
                      13, kAccentDark, gfx::Align::left, 1.5f);
        hui::ui::text(draw, context_.fonts.display, level.title, 118, 267, 26, kInk);
        hui::ui::paragraph(draw, context_.fonts.regular, level.objective, 118, 300, 15,
                           1570, 19, kMuted, 2);

        draw.bordered_rect(Rect{112, 350, 802, 524}, 20, kPanel, 1.2f, kBorder);
        hui::ui::text(draw, context_.fonts.semibold, "CESTA DE ROPA", 140, 385, 13,
                      kAccentDark, gfx::Align::left, 1.2f);
        char labels[48]{};
        int read = 0;
        for (const auto &item : session_.items()) read += item.label_read ? 1 : 0;
        std::snprintf(labels, sizeof(labels), "ETIQUETAS LEÍDAS %d / %d", read,
                      static_cast<int>(session_.items().size()));
        hui::ui::text(draw, context_.fonts.semibold, labels, 884, 385, 11, kMuted,
                      gfx::Align::right, 0.6f);
        for (std::size_t i = 0; i < level.garments.size(); ++i)
        {
            const int col = static_cast<int>(i % 2);
            const int row = static_cast<int>(i / 2);
            const Rect card{136.0f + col*382.0f, 410.0f + row*105.0f, 360.0f, 90.0f};
            const bool selected = i == selected_garment_;
            const game::ItemState &state = session_.items()[i];
            draw.bordered_rect(card, 13, selected ? kSelected : Color::rgb(0xffffff),
                               selected ? 2.0f : 1.0f, selected ? kAccent : kBorder);
            draw_garment_image(draw, level.garments[i].id,
                               Rect{card.x + 4, card.y + 5, 68, 78}, garment_atlases_);
            hui::ui::paragraph(draw, context_.fonts.semibold, level.garments[i].name,
                               card.x + 75, card.y + 28, 13, card.w - 88, 16, kInk, 2);
            const char *where = state.loaded ? "EN TAMBOR" : "EN CESTA";
            const Color where_color = state.loaded ? kAccentDark : kMuted;
            hui::ui::text(draw, context_.fonts.semibold, where, card.x + 75, card.y + 70,
                          9, where_color, gfx::Align::left, 0.7f);
            hui::ui::text(draw, context_.fonts.regular,
                state.label_read ? "ETIQUETA LEÍDA" : "ETIQUETA PENDIENTE",
                card.x + card.w - 10, card.y + 70, 9,
                state.label_read ? kGood : kWarn, gfx::Align::right, 0.4f);
            if (state.in_mesh)
                draw.rounded_rect(Rect{card.x + card.w - 35, card.y + 8, 24, 18}, 6,
                                  Color::rgb(0xe9def4));
            if (level.garments[i].stain != game::Stain::none)
                draw.circle(card.x + 59, card.y + 75, 4, Color::rgb(0xb65c45));
        }

        draw.bordered_rect(Rect{940, 350, 862, 524}, 20, Color::rgb(0xf4f8f9), 1.2f, kBorder);
        draw_machine(draw, context_.fonts, Rect{968, 375, 330, 474}, &level, &session_.items(),
                     session_.animation(), session_.door_open(), nullptr,
                     context_.settings.reduced_motion, garment_atlases_);
        hui::ui::text(draw, context_.fonts.semibold, "CAPACIDAD TOTAL", 1342, 396, 12,
                      kAccentDark, gfx::Align::left, 1.0f);
        hui::ui::text(draw, context_.fonts.regular, "Lavadora estándar de 8 kg", 1342, 423,
                      15, kInk);
        const int load = session_.load_weight_grams();
        const float ratio = std::clamp(static_cast<float>(load) /
                                      static_cast<float>(game::kGarmentCapacityGrams), 0.0f, 1.0f);
        char load_line[96]{};
        std::snprintf(load_line, sizeof(load_line), "Prendas %s / 6.000 kg",
                      weight_text(load).c_str());
        hui::ui::text(draw, context_.fonts.semibold, load_line, 1342, 461, 15,
                      ratio > 0.88f ? kWarn : kAccentDark);
        draw.rounded_rect(Rect{1342, 478, 396, 11}, 5, Color::rgb(0xd4e1e7));
        draw.rounded_rect(Rect{1342, 478, 396*ratio, 11}, 5,
                          ratio > 0.88f ? Color::rgb(0xd69b39) : kAccent);
        char remaining[64]{};
        std::snprintf(remaining, sizeof(remaining), "DISPONIBLE %s PARA PRENDAS",
                      weight_text(session_.remaining_weight_grams()).c_str());
        hui::ui::text(draw, context_.fonts.regular, remaining, 1342, 505, 10, kMuted);
        draw.bordered_rect(Rect{1342, 516, 396, 84}, 14, Color::rgb(0xffffff), 1, kBorder);
        hui::ui::text(draw, context_.fonts.semibold, "AGUA FIJA", 1360, 545, 10, kMuted,
                      gfx::Align::left, 1.0f);
        hui::ui::text(draw, context_.fonts.semibold, "2.000 kg", 1718, 547, 15, kAccentDark,
                      gfx::Align::right);
        char total[80]{};
        std::snprintf(total, sizeof(total), "TOTAL EN TAMBOR  %s / 8.000 kg",
                      weight_text(load + game::kCycleWaterGrams).c_str());
        hui::ui::text(draw, context_.fonts.semibold, total, 1342, 639, 13, kInk);
        draw.line(1342, 660, 1738, 660, 1, kBorder);
        hui::ui::paragraph(draw, context_.fonts.regular,
            "La carga máxima incluye el agua. Antes del ciclo se reservan 2 kg para agua: quedan 6 kg para prendas.",
            1342, 691, 13, 390, 18, kMuted, 4);
        char mesh[48]{};
        int mesh_count = 0;
        for (const auto &item : session_.items()) mesh_count += item.in_mesh ? 1 : 0;
        std::snprintf(mesh, sizeof(mesh), "EN BOLSA DE MALLA: %d", mesh_count);
        hui::ui::text(draw, context_.fonts.semibold, mesh, 1342, 825, 11, kAccentDark,
                      gfx::Align::left, 0.6f);
        if (!status_.empty())
            hui::ui::paragraph(draw, context_.fonts.semibold, status_, 120, 914, 12,
                               1640, 16, kWarn, 1);
        draw_footer(draw, "Flechas: prenda     L1/R1: anterior/siguiente     X: cargar / retirar     Touchpad / R3: etiqueta     CUADRADO: malla / mancha     L3: puerta     TRIÁNGULO: manual     R2: ajustes     O: pausa");
    }

    void draw_machine_setup(gfx::DrawList &draw) const
    {
        const auto &level = session_.level();
        const MachineSettings &settings = session_.machine_settings();
        draw.bordered_rect(Rect{82, 188, 1756, 746}, 26, Color::rgb(0xf9fbfc), 1.5f, kBorder);
        hui::ui::text(draw, context_.fonts.semibold, "PANEL DE LAVADO", 118, 226, 13,
                      kAccentDark, gfx::Align::left, 1.5f);
        hui::ui::text(draw, context_.fonts.display, "Configura la lavadora", 118, 268, 28, kInk);
        draw_machine(draw, context_.fonts, Rect{120, 308, 340, 560}, &level, &session_.items(),
                     session_.animation(), session_.door_open(), &settings,
                     context_.settings.reduced_motion, garment_atlases_);
        char caps[120]{};
        std::snprintf(caps, sizeof(caps), "LÍMITES DE LA CARGA: %d °C MÁX.   ·   %d RPM MÁX.",
                      session_.effective_max_temperature_c(), session_.effective_max_spin_rpm());
        hui::ui::text(draw, context_.fonts.semibold, caps, 514, 292, 14, kAccentDark,
                      gfx::Align::left, 0.4f);
        draw.line(514, 307, 1770, 307, 1, kBorder);

        const game::StartBlock block = session_.start_block();
        const std::array<std::string_view, 8> names = {
            "Puerta", "Programa", "Temperatura", "Centrifugado", "Detergente",
            "Suavizante", "Aditivo / lejía", "Iniciar lavado"};
        const std::array<std::string_view, 8> values = {
            session_.door_open() ? "ABIERTA" : "CERRADA",
            settings.program_selected ? game::program_name(settings.program) : "POR ELEGIR",
            settings.temperature_selected ? temp_name(settings.temperature_c) : "POR ELEGIR",
            settings.spin_selected ? spin_name(settings.spin_rpm) : "POR ELEGIR",
            settings.detergent_selected ? game::detergent_name(settings.detergent) : "POR ELEGIR",
            settings.softener_selected ? game::softener_name(settings.softener) : "POR ELEGIR",
            settings.additive_selected ? game::additive_name(settings.additive) : "POR ELEGIR",
            block == game::StartBlock::none ? "PULSA X PARA INICIAR" : "REVISA LA PREPARACIÓN"};
        for (int i = 0; i < 8; ++i)
        {
            const float y = 328.0f + i*71.0f;
            const Rect row{514, y, 1256, 61};
            const bool selected = control_index_ == i;
            draw.bordered_rect(row, 13, selected ? kSelected : Color::rgb(0xffffff),
                               selected ? 2.0f : 1.0f, selected ? kAccent : kBorder);
            hui::ui::text(draw, context_.fonts.mono, i == 7 ? "GO" : "0" + std::to_string(i + 1),
                          row.x + 20, row.y + 37, 12, selected ? kAccentDark : kMuted);
            hui::ui::text(draw, context_.fonts.semibold, names[static_cast<std::size_t>(i)],
                          row.x + 76, row.y + 38, 16, kInk);
            hui::ui::text(draw, context_.fonts.semibold, values[static_cast<std::size_t>(i)],
                          row.x + row.w - 20, row.y + 38, 14,
                          selected ? kAccentDark : kMuted, gfx::Align::right);
        }
        const Color status_color = block == game::StartBlock::none ? kGood : kWarn;
        hui::ui::text(draw, context_.fonts.regular,
                      block == game::StartBlock::none && !status_.empty()
                          ? std::string_view(status_)
                          : game::start_block_message(block),
                      514, 917, 12, status_color);
        draw_footer(draw, "Flechas: recorrer / cambiar ajuste     L1/R1: ajuste anterior/siguiente     X: elegir / cerrar / iniciar     R2: iniciar     L2: prendas     Touchpad / TRIÁNGULO: manual     R3: etiqueta     O: pausa");
    }

    static std::string_view temp_name(int value)
    {
        if (value == 20) return "Frío · 20 °C";
        char text[20]{};
        std::snprintf(text, sizeof(text), "%d °C", value);
        temp_buffer_ = text;
        return temp_buffer_;
    }

    static std::string_view spin_name(int value)
    {
        if (value == 0) return "Sin centrifugado";
        char text[24]{};
        std::snprintf(text, sizeof(text), "%d RPM", value);
        spin_buffer_ = text;
        return spin_buffer_;
    }

    void draw_cycle(gfx::DrawList &draw) const
    {
        const auto &level = session_.level();
        draw.bordered_rect(Rect{82, 188, 1756, 746}, 26, Color::rgb(0xf9fbfc), 1.5f, kBorder);
        hui::ui::text(draw, context_.fonts.semibold, "CICLO EN MARCHA", 124, 226, 13,
                      kAccentDark, gfx::Align::left, 1.6f);
        hui::ui::text(draw, context_.fonts.display, level.title, 124, 271, 27, kInk);
        draw_machine(draw, context_.fonts, Rect{280, 305, 470, 570}, &level, &session_.items(),
                     session_.animation(), false, &session_.machine_settings(),
                     context_.settings.reduced_motion, garment_atlases_);
        hui::ui::text(draw, context_.fonts.semibold,
                      game::cycle_phase_name(session_.animation().phase), 862, 390, 18,
                      kAccentDark, gfx::Align::left, 0.8f);
        const float ratio = std::clamp(session_.animation().cycle_seconds / 16.6f, 0.0f, 1.0f);
        draw.rounded_rect(Rect{862, 418, 760, 13}, 6, Color::rgb(0xd4e1e7));
        draw.rounded_rect(Rect{862, 418, 760*ratio, 13}, 6, kAccent);
        const std::array<std::string_view, 4> phases = {"LLENADO", "LAVADO", "ACLARADO", "CENTRIFUGADO"};
        const std::array<game::CyclePhase, 4> active = {game::CyclePhase::filling,
            game::CyclePhase::washing, game::CyclePhase::rinsing, game::CyclePhase::spinning};
        for (int i = 0; i < 4; ++i)
        {
            const float x = 862.0f + i*195.0f;
            const bool reached = static_cast<int>(session_.animation().phase) >= static_cast<int>(active[i]);
            draw.circle(x + 12, 488, 11, reached ? kAccent : Color::rgb(0xe2e9ec));
            hui::ui::text(draw, context_.fonts.semibold, std::to_string(i + 1), x + 12, 493,
                          10, reached ? Color::rgb(0xffffff) : kMuted, gfx::Align::center);
            hui::ui::text(draw, context_.fonts.semibold, phases[static_cast<std::size_t>(i)],
                          x + 31, 493, 10, reached ? kAccentDark : kMuted,
                          gfx::Align::left, 0.3f);
        }
        char timer[48]{};
        const float remaining = std::max(0.0f, 16.6f - session_.animation().cycle_seconds);
        std::snprintf(timer, sizeof(timer), "00:%02d", static_cast<int>(std::ceil(remaining)));
        hui::ui::text(draw, context_.fonts.mono, timer, 1240, 625, 30, kInk,
                      gfx::Align::center);
        hui::ui::text(draw, context_.fonts.regular, "Tiempo restante", 1240, 655, 13,
                      kMuted, gfx::Align::center);
        hui::ui::paragraph(draw, context_.fonts.regular,
            "El tambor cambia de ritmo entre lavado, aclarado y centrifugado. La carga de agua permanece en el cálculo de capacidad.",
            862, 730, 15, 748, 21, kMuted, 3);
        draw_footer(draw, "Touchpad: consultar manual y pausar el ciclo     Options: pausar / continuar");
    }

    void draw_report(gfx::DrawList &draw) const
    {
        draw.bordered_rect(Rect{88, 194, 1744, 708}, 28, Color::rgb(0xf9fbfc), 1.5f, kBorder);
        const auto &level = session_.level();
        hui::ui::text(draw, context_.fonts.semibold, "INFORME DE LAVADO", 140, 248, 14,
                      kAccentDark, gfx::Align::left, 1.8f);
        hui::ui::text(draw, context_.fonts.display, level.title, 140, 291, 28, kInk);
        char score[72]{};
        std::snprintf(score, sizeof(score), "%d / 300 puntos", result_.score);
        hui::ui::text(draw, context_.fonts.semibold, score, 140, 343, 20, kAccentDark);
        for (int i = 0; i < 3; ++i)
            draw.star(1600.0f + i*38.0f, 335.0f, 13.0f,
                      i < result_.stars ? Color::rgb(0xe1ae35) : Color::rgb(0xd2dce0),
                      i < result_.stars ? 0.0f : 1.5f);
        draw.bordered_rect(Rect{140, 378, 1640, 285}, 18, Color::rgb(0xffffff), 1, kBorder);
        float baseline = 416;
        const std::size_t visible = std::min<std::size_t>(result_.feedback.size(), 7);
        if (visible == 0)
            hui::ui::text(draw, context_.fonts.regular, "Ciclo completado.", 170, baseline, 16, kMuted);
        for (std::size_t i = 0; i < visible; ++i)
        {
            baseline = hui::ui::paragraph(draw, context_.fonts.regular, result_.feedback[i],
                170, baseline, 14, 1550, 19,
                result_.perfect ? kGood : kInk, 2) + 7;
        }
        const bool has_next = session_.level_index() + 1 < game::kLevelCount;
        const std::array<std::string_view, 4> actions = has_next
            ? std::array<std::string_view, 4>{"Siguiente nivel", "Repetir misión", "Mapa de niveles", "Volver al menú"}
            : std::array<std::string_view, 4>{"Repetir misión", "Mapa de niveles", "Volver al menú", ""};
        const int count = has_next ? 4 : 3;
        for (int i = 0; i < count; ++i)
        {
            const float x = has_next ? 140.0f + i*410.0f : 260.0f + i*500.0f;
            const Rect button{x, 704, has_next ? 370.0f : 430.0f, 78};
            const bool selected = selected_result_ == i;
            draw.bordered_rect(button, 14, selected ? kSelected : Color::rgb(0xffffff),
                               selected ? 2 : 1, selected ? kAccent : kBorder);
            hui::ui::text(draw, context_.fonts.semibold, actions[static_cast<std::size_t>(i)],
                          button.cx(), button.y + 47, 15, selected ? kAccentDark : kInk,
                          gfx::Align::center);
        }
        if (!status_.empty())
            hui::ui::text(draw, context_.fonts.regular, status_, 140, 843, 12, kMuted);
        draw_footer(draw, has_next && selected_result_ == 0
            ? "Flechas: elegir acción     X: iniciar siguiente nivel     O: mapa"
            : "Flechas: elegir acción     X: confirmar opción     O: mapa");
    }

    void draw_return_screen(gfx::DrawList &draw) const
    {
        if (screen_ == Screen::pause)
        {
            if (pause_return_ == Screen::sorting) draw_sorting(draw);
            else if (pause_return_ == Screen::machine) draw_machine_setup(draw);
            else if (pause_return_ == Screen::running) draw_cycle(draw);
            else if (pause_return_ == Screen::levels) draw_levels(draw);
            else draw_home(draw);
            return;
        }
        if (return_screen_ == Screen::sorting)
            draw_sorting(draw);
        else if (return_screen_ == Screen::machine)
            draw_machine_setup(draw);
        else if (return_screen_ == Screen::label)
        {
            draw_sorting(draw);
            draw_label(draw);
        }
        else if (return_screen_ == Screen::running)
            draw_cycle(draw);
        else
            draw_home(draw);
    }

    void draw_overlay_panel(gfx::DrawList &draw, const Rect &panel) const
    {
        draw.rounded_rect(Rect{82, 180, 1756, 760}, 26, Color::rgb(0x10212b, 0.48f));
        draw.shadow(panel, 22, 24, Color::rgb(0x10212b, 0.22f));
        draw.bordered_rect(panel, 22, Color::rgb(0xffffff), 1.5f, kBorder);
    }

    void draw_label(gfx::DrawList &draw) const
    {
        draw_overlay_panel(draw, Rect{310, 222, 1300, 670});
        const auto &garment = session_.level().garments[selected_garment_];
        hui::ui::text(draw, context_.fonts.semibold, "ETIQUETA DE CUIDADO", 370, 277, 14,
                      kAccentDark, gfx::Align::left, 1.5f);
        hui::ui::text(draw, context_.fonts.display, garment.name, 370, 324, 29, kInk);
        draw.rounded_rect(Rect{370, 353, 120, 6}, 3, kAccent);
        draw_garment_image(draw, garment.id, Rect{370, 400, 220, 230}, garment_atlases_);
        hui::ui::text(draw, context_.fonts.semibold, game::fabric_name(garment.fabric),
                      520, 658, 15, kMuted, gfx::Align::center);

        const bool softener_avoid = garment.fabric == game::Fabric::sport ||
            garment.fabric == game::Fabric::down || garment.fabric == game::Fabric::wool ||
            garment.fabric == game::Fabric::silk || garment.fabric == game::Fabric::delicate;
        const std::string softener_guidance = garment.baby_sensitive
            ? "Hipoalergénico o ninguno"
            : softener_avoid ? "Evitar en este tejido" : "Según la misión";
        const std::array<std::string_view, 8> labels = {
            "Peso en seco", "Lavado máximo", "Centrifugado máximo", "Tejido y composición",
            "Blanqueador", "Suavizante", "Mancha", "Protección"};
        const std::string bleach = garment.bleach == game::BleachAllowance::any ? "Oxígeno o cloro permitidos"
            : garment.bleach == game::BleachAllowance::oxygen_only ? "Solo oxígeno activo; nunca cloro"
                                                                    : "No usar lejía";
        const std::string protection = garment.needs_mesh ? "Usar bolsa de malla"
            : garment.machine_washable ? "Lavable a máquina" : "No lavar a máquina";
        const std::array<std::string, 8> values = {
            weight_text(garment.weight_grams),
            garment.machine_washable ? std::to_string(garment.max_temperature_c) + " °C" : "No lavar a máquina",
            garment.machine_washable ? std::to_string(garment.max_spin_rpm) + " RPM" : "Sin centrifugado",
            std::string(game::fabric_name(garment.fabric)) + " · " +
                std::string(game::color_name(garment.color)) + " · " +
                std::string(garment.composition),
            bleach,
            softener_guidance,
            std::string(game::stain_name(garment.stain)),
            protection};
        for (int i = 0; i < 8; ++i)
        {
            const float y = 386.0f + i*54.0f;
            draw.bordered_rect(Rect{700, y, 850, 45}, 11, Color::rgb(0xf8fafb), 1, kBorder);
            hui::ui::text(draw, context_.fonts.regular, labels[static_cast<std::size_t>(i)],
                          720, y + 29, 12, kMuted);
            hui::ui::paragraph(draw, context_.fonts.semibold, values[static_cast<std::size_t>(i)],
                               930, y + 29, 13, 600, 16, kInk, 1);
        }
        hui::ui::text(draw, context_.fonts.regular,
                      "Peso orientativo para la simulación; la etiqueta real de cada prenda prevalece.",
                      700, 856, 11, kMuted);
        draw_footer(draw, "X: confirmar lectura de etiqueta     O: volver     TRIÁNGULO: manual breve");
    }

    void draw_treatment(gfx::DrawList &draw) const
    {
        draw_overlay_panel(draw, Rect{470, 250, 980, 595});
        const auto &garment = session_.level().garments[selected_garment_];
        const game::ItemState *item = session_.item_state(selected_garment_);
        hui::ui::text(draw, context_.fonts.semibold,
                      garment.needs_mesh ? "CUIDADO DE PRENDA" : "PRETRATAMIENTO", 530, 307, 14,
                      kAccentDark, gfx::Align::left, 1.5f);
        hui::ui::text(draw, context_.fonts.display, std::string(game::stain_name(garment.stain)) +
                      " · " + std::string(garment.name), 530, 355, 23, kInk);
        hui::ui::text(draw, context_.fonts.regular,
                      garment.needs_mesh
                          ? "Elige el tratamiento y prepara también la bolsa de malla."
                          : "Elige el producto o procedimiento para esta mancha.",
                      530, 391, 15, kMuted);
        const std::size_t row_count = kTreatments.size() + (garment.needs_mesh ? 1u : 0u);
        for (std::size_t i = 0; i < row_count; ++i)
        {
            const Rect row{530, 425.0f + static_cast<float>(i)*64.0f, 860, 52};
            const bool selected = selected_treatment_ == i;
            draw.bordered_rect(row, 12, selected ? kSelected : Color::rgb(0xffffff),
                               selected ? 2 : 1, selected ? kAccent : kBorder);
            std::string_view label;
            if (i < kTreatments.size())
                label = game::treatment_name(kTreatments[i]);
            else
                label = item != nullptr && item->in_mesh
                    ? "Bolsa de malla: retirar la prenda"
                    : "Bolsa de malla: colocar la prenda";
            hui::ui::text(draw, context_.fonts.semibold, label, row.x + 24,
                          row.y + 33, 14, selected ? kAccentDark : kInk);
        }
        draw_footer(draw, garment.needs_mesh
            ? "Flechas: elegir     X: aplicar / alternar malla     O: volver"
            : "Flechas: elegir producto     X: aplicar a esta prenda     O: volver");
    }

    void draw_manual(gfx::DrawList &draw) const
    {
        draw_overlay_panel(draw, Rect{330, 210, 1260, 700});
        hui::ui::text(draw, context_.fonts.semibold, "MANUAL BREVE DE BOLSILLO", 390, 270, 14,
                      kAccentDark, gfx::Align::left, 1.6f);
        hui::ui::text(draw, context_.fonts.display, "Lee la etiqueta antes de lavar", 390, 318,
                      28, kInk);
        const std::array<std::pair<std::string_view, std::string_view>, 5> sections = {{
            {"CAPACIDAD", "Lavadora de 8 kg. El ciclo reserva 2 kg para agua; carga hasta 6 kg de prendas secas."},
            {"TEMPERATURA Y GIRO", "Cada prenda marca sus máximos. La carga completa adopta el menor límite de temperatura y de centrifugado."},
            {"DETERGENTE", "Elige el producto por tejido y color. Lana, prendas delicadas y ropa técnica necesitan productos compatibles."},
            {"SUAVIZANTE Y LEJÍA", "El suavizante puede dañar microfibras deportivas y acolchados. Usa lejía solo si la etiqueta lo permite; el cloro no sustituye al oxígeno activo."},
            {"MANCHAS Y MALLA", "Trata la mancha antes de cargar. Las prendas con piezas pequeñas o delicadas deben ir en bolsa de malla cuando su etiqueta lo indique."},
        }};
        for (std::size_t i = 0; i < sections.size(); ++i)
        {
            const float y = 365.0f + static_cast<float>(i)*91.0f;
            draw.rounded_rect(Rect{390, y - 16, 5, 62}, 2, kAccent);
            hui::ui::text(draw, context_.fonts.semibold, sections[i].first, 416, y, 11,
                          kAccentDark, gfx::Align::left, 1.1f);
            hui::ui::paragraph(draw, context_.fonts.regular, sections[i].second, 416, y + 24,
                               14, 1080, 18, kMuted, 2);
        }
        draw_footer(draw, "Touchpad / X / O: volver a la misión");
    }

    void draw_pause(gfx::DrawList &draw) const
    {
        draw_overlay_panel(draw, Rect{540, 310, 840, 465});
        hui::ui::text(draw, context_.fonts.semibold, "MISIÓN EN PAUSA", 600, 366, 14,
                      kAccentDark, gfx::Align::left, 1.5f);
        const std::array<std::string_view, 4> actions = {
            "Continuar", "Reiniciar nivel", "Mapa de niveles", "Menú principal"};
        for (int i = 0; i < 4; ++i)
        {
            const float y = 404.0f + i*70.0f;
            const bool selected = selected_pause_ == i;
            draw.bordered_rect(Rect{600, y, 720, 54}, 12,
                selected ? kSelected : Color::rgb(0xffffff), selected ? 2 : 1,
                selected ? kAccent : kBorder);
            hui::ui::text(draw, context_.fonts.semibold, actions[static_cast<std::size_t>(i)],
                          630, y + 34, 15, selected ? kAccentDark : kInk);
        }
        draw_footer(draw, "Flechas: elegir     X: confirmar     O / Options: continuar");
    }

    app::Context &context_;
    GarmentAtlases garment_atlases_{};
    game::PersistentProgress progress_;
    LaundrySession session_;
    Evaluation result_;
    Screen screen_ = Screen::home;
    Screen return_screen_ = Screen::sorting;
    Screen pause_return_ = Screen::sorting;
    std::size_t selected_home_ = 0;
    std::size_t selected_setting_ = 0;
    std::size_t selected_level_ = 0;
    std::size_t selected_garment_ = 0;
    std::size_t selected_treatment_ = 0;
    int control_index_ = 0;
    int selected_pause_ = 0;
    int selected_result_ = 0;
    std::string status_;
    static inline std::string temp_buffer_;
    static inline std::string spin_buffer_;
};

} // namespace

std::unique_ptr<app::Concept> make_taller_menu(app::Context &context)
{
    return std::make_unique<TallerMenu>(context);
}

} // namespace hui::concepts
