// Maestro Lavandero: rules, cycle simulation and persistent progress.
// Copyright (C) 2026 BlackBearReloaded
// SPDX-License-Identifier: GPL-3.0-or-later

#include "game/laundry_game.hpp"

#include "core/bytes.hpp"
#include "core/save_file.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <utility>

namespace hui::game
{
namespace
{
constexpr std::uint8_t kProgressVersion = 1;
constexpr std::string_view kProgressFile = "/maestro-lavandero-progress.bin";
constexpr float kFillSeconds = 2.6f;
constexpr float kWashSeconds = 5.4f;
constexpr float kRinseSeconds = 3.8f;
constexpr float kSpinSeconds = 4.8f;
constexpr float kTotalCycleSeconds = kFillSeconds + kWashSeconds + kRinseSeconds + kSpinSeconds;

float clamp01(float value)
{
    return std::clamp(value, 0.0f, 1.0f);
}

float smooth(float value)
{
    const float t = clamp01(value);
    return t * t * (3.0f - 2.0f * t);
}

void penalize(Evaluation &result, int amount, std::string text)
{
    result.score -= amount;
    result.feedback.push_back(std::move(text));
}

Treatment treatment_for(Stain stain)
{
    switch (stain)
    {
    case Stain::oil:
        return Treatment::grease_remover;
    case Stain::blood:
        return Treatment::cold_enzyme;
    case Stain::mud:
        return Treatment::brush_prewash;
    case Stain::wine:
        return Treatment::oxygen_spotter;
    case Stain::none:
        return Treatment::none;
    }
    return Treatment::none;
}

bool additive_safe_for(const GarmentDefinition &garment, Additive additive)
{
    switch (additive)
    {
    case Additive::none:
    case Additive::color_protect:
        return true;
    case Additive::oxygen_bleach:
        return garment.bleach == BleachAllowance::oxygen_only ||
               garment.bleach == BleachAllowance::any;
    case Additive::chlorine_bleach:
        return garment.bleach == BleachAllowance::any;
    case Additive::unselected:
        return false;
    }
    return false;
}

bool detergent_safe_for(const GarmentDefinition &garment, Detergent detergent)
{
    switch (detergent)
    {
    case Detergent::unselected:
        return false;
    case Detergent::none:
    case Detergent::eco:
        return true;
    case Detergent::universal:
    case Detergent::color:
        return garment.fabric != Fabric::wool && garment.fabric != Fabric::silk &&
               garment.fabric != Fabric::delicate && garment.fabric != Fabric::sport &&
               garment.fabric != Fabric::down && garment.fabric != Fabric::leather;
    case Detergent::wool:
        return garment.fabric == Fabric::wool || garment.fabric == Fabric::silk ||
               garment.fabric == Fabric::delicate;
    case Detergent::sport:
        return garment.fabric == Fabric::sport || garment.fabric == Fabric::synthetic;
    }
    return false;
}

bool program_safe_for(const GarmentDefinition &garment, Program program)
{
    switch (program)
    {
    case Program::unselected:
        return false;
    case Program::cotton:
        return garment.fabric != Fabric::wool && garment.fabric != Fabric::silk &&
               garment.fabric != Fabric::delicate && garment.fabric != Fabric::sport &&
               garment.fabric != Fabric::down && garment.fabric != Fabric::leather;
    case Program::synthetics:
        return garment.fabric != Fabric::wool && garment.fabric != Fabric::silk &&
               garment.fabric != Fabric::delicate && garment.fabric != Fabric::down &&
               garment.fabric != Fabric::leather;
    case Program::delicates:
        return garment.fabric != Fabric::leather && garment.fabric != Fabric::denim;
    case Program::wool:
        return garment.fabric == Fabric::wool || garment.fabric == Fabric::silk ||
               garment.fabric == Fabric::delicate;
    case Program::sport:
        return garment.fabric == Fabric::sport || garment.fabric == Fabric::synthetic;
    case Program::quick:
        return garment.lightly_used && garment.stain == Stain::none &&
               garment.fabric != Fabric::wool && garment.fabric != Fabric::silk &&
               garment.fabric != Fabric::delicate && garment.fabric != Fabric::down &&
               garment.fabric != Fabric::leather;
    case Program::eco:
        return garment.eco_compatible;
    }
    return false;
}

bool load_has_mixed_color(const LevelDefinition &level, const std::vector<ItemState> &items)
{
    bool saw_white = false;
    bool saw_dark = false;
    bool saw_color = false;
    for (std::size_t i = 0; i < items.size(); ++i)
    {
        if (!items[i].loaded)
            continue;
        switch (level.garments[i].color)
        {
        case TextileColor::white:
            saw_white = true;
            break;
        case TextileColor::dark:
            saw_dark = true;
            break;
        case TextileColor::color:
            saw_color = true;
            break;
        }
    }
    return (saw_white && (saw_dark || saw_color)) || (saw_dark && saw_color);
}

int program_temperature_limit(Program program)
{
    switch (program)
    {
    case Program::cotton:
        return 90;
    case Program::synthetics:
    case Program::sport:
        return 60;
    case Program::delicates:
    case Program::wool:
    case Program::quick:
        return 40;
    case Program::eco:
        return 60;
    case Program::unselected:
        return 0;
    }
    return 0;
}

int program_spin_limit(Program program)
{
    switch (program)
    {
    case Program::cotton:
    case Program::eco:
        return 1400;
    case Program::synthetics:
    case Program::sport:
        return 1200;
    case Program::delicates:
    case Program::wool:
        return 800;
    case Program::quick:
        return 1000;
    case Program::unselected:
        return 0;
    }
    return 0;
}

} // namespace

int PersistentProgress::total_best_score() const
{
    int total = 0;
    for (std::uint16_t score : best_scores)
        total += score;
    return total;
}

void PersistentProgress::record(std::size_t level_index, const Evaluation &evaluation)
{
    if (level_index >= kLevelCount)
        return;
    completed_mask |= (1u << level_index);
    const std::size_t next = std::min(level_index + 1, kLevelCount - 1);
    unlocked_through = static_cast<std::uint8_t>(std::max<std::size_t>(unlocked_through, next));
    const int score = std::clamp(evaluation.score, 0, 300);
    const int stars = std::clamp(evaluation.stars, 0, 3);
    best_scores[level_index] = static_cast<std::uint16_t>(
        std::max<int>(best_scores[level_index], score));
    best_stars[level_index] = static_cast<std::uint8_t>(
        std::max<int>(best_stars[level_index], stars));
}

PersistentProgress load_progress(std::string_view save_root)
{
    PersistentProgress progress;
    if (save_root.empty())
        return progress;
    const std::string path = std::string(save_root) + std::string(kProgressFile);
    std::string encoded;
    if (!save::read_file(path, &encoded, 1024))
        return progress;
    const save::Decoded decoded = save::decode(save::Kind::game, encoded);
    if (!decoded.ok || decoded.version != 1)
        return progress;

    bytes::Reader reader(decoded.payload);
    if (reader.get<std::uint8_t>() != kProgressVersion)
        return progress;
    const std::uint8_t unlocked = reader.get<std::uint8_t>();
    const std::uint32_t completed = reader.get<std::uint32_t>();
    PersistentProgress candidate;
    candidate.unlocked_through = unlocked;
    candidate.completed_mask = completed;
    for (std::size_t i = 0; i < kLevelCount; ++i)
    {
        candidate.best_scores[i] = reader.get<std::uint16_t>();
        candidate.best_stars[i] = reader.get<std::uint8_t>();
    }
    if (!reader.finished() || candidate.unlocked_through >= kLevelCount ||
        (candidate.completed_mask >> kLevelCount) != 0)
        return progress;
    for (std::size_t i = 0; i < kLevelCount; ++i)
    {
        if (candidate.best_scores[i] > 300 || candidate.best_stars[i] > 3)
            return progress;
    }
    return candidate;
}

bool save_progress(std::string_view save_root, const PersistentProgress &progress)
{
    if (save_root.empty())
        return false;
    const std::string root(save_root);
    if (!save::ensure_directory(root))
        return false;
    bytes::Writer writer;
    writer.put(kProgressVersion);
    writer.put(static_cast<std::uint8_t>(
        std::min<std::size_t>(progress.unlocked_through, kLevelCount - 1)));
    writer.put(progress.completed_mask & ((1u << kLevelCount) - 1u));
    for (std::size_t i = 0; i < kLevelCount; ++i)
    {
        writer.put<std::uint16_t>(std::min<std::uint16_t>(progress.best_scores[i], 300));
        writer.put<std::uint8_t>(std::min<std::uint8_t>(progress.best_stars[i], 3));
    }
    const std::string path = root + std::string(kProgressFile);
    const std::string container = save::encode(save::Kind::game, 1, writer.data());
    return save::write_atomic(path, container).empty();
}

void LaundrySession::begin_level(std::size_t index)
{
    const std::span<const LevelDefinition> catalog = level_catalog();
    if (catalog.empty())
    {
        level_ = nullptr;
        level_index_ = 0;
        items_.clear();
        machine_ = {};
        animation_ = {};
        door_open_ = true;
        return;
    }
    level_index_ = std::min(index, catalog.size() - 1);
    level_ = &catalog[level_index_];
    // Every run starts clean. Only PersistentProgress survives a level change.
    items_.assign(level_->garments.size(), ItemState{});
    machine_ = {};
    animation_ = {};
    door_open_ = true;
}

const LevelDefinition &LaundrySession::level() const
{
    const std::span<const LevelDefinition> catalog = level_catalog();
    return level_ != nullptr ? *level_ : catalog.front();
}

std::size_t LaundrySession::level_index() const
{
    return level_index_;
}

const std::vector<ItemState> &LaundrySession::items() const
{
    return items_;
}

ItemState *LaundrySession::item_state(std::size_t index)
{
    return index < items_.size() ? &items_[index] : nullptr;
}

const ItemState *LaundrySession::item_state(std::size_t index) const
{
    return index < items_.size() ? &items_[index] : nullptr;
}

MachineSettings &LaundrySession::machine_settings()
{
    return machine_;
}

const MachineSettings &LaundrySession::machine_settings() const
{
    return machine_;
}

CycleAnimation &LaundrySession::animation()
{
    return animation_;
}

const CycleAnimation &LaundrySession::animation() const
{
    return animation_;
}

bool LaundrySession::door_open() const
{
    return door_open_;
}

void LaundrySession::set_door_open(bool open)
{
    if (animation_.phase == CyclePhase::idle || animation_.phase == CyclePhase::complete)
        door_open_ = open;
}

MoveResult LaundrySession::move_item(std::size_t index)
{
    if (index >= items_.size() || level_ == nullptr)
        return MoveResult::invalid_item;
    if (!door_open_)
        return MoveResult::door_closed;
    ItemState &state = items_[index];
    if (state.loaded)
    {
        state.loaded = false;
        return MoveResult::unloaded;
    }
    if (!state.label_read)
        return MoveResult::label_not_read;
    if (load_weight_grams() + level_->garments[index].weight_grams > kGarmentCapacityGrams)
        return MoveResult::capacity_exceeded;
    state.loaded = true;
    return MoveResult::loaded;
}

bool LaundrySession::mark_label_read(std::size_t index)
{
    ItemState *state = item_state(index);
    if (state == nullptr)
        return false;
    state->label_read = true;
    return true;
}

bool LaundrySession::toggle_mesh(std::size_t index)
{
    if (level_ == nullptr || index >= items_.size() || !level_->garments[index].needs_mesh ||
        !door_open_ || items_[index].loaded || !items_[index].label_read)
        return false;
    items_[index].in_mesh = !items_[index].in_mesh;
    return true;
}

bool LaundrySession::choose_treatment(std::size_t index, Treatment treatment)
{
    if (level_ == nullptr || index >= items_.size() || level_->garments[index].stain == Stain::none)
        return false;
    if (!door_open_ || items_[index].loaded || !items_[index].label_read)
        return false;
    items_[index].treatment = treatment;
    return true;
}

int LaundrySession::loaded_garments() const
{
    return static_cast<int>(std::count_if(items_.begin(), items_.end(),
                                          [](const ItemState &item) { return item.loaded; }));
}

int LaundrySession::load_weight_grams() const
{
    if (level_ == nullptr)
        return 0;
    int total = 0;
    const std::size_t count = std::min(items_.size(), level_->garments.size());
    for (std::size_t i = 0; i < count; ++i)
        if (items_[i].loaded)
            total += level_->garments[i].weight_grams;
    return total;
}

int LaundrySession::remaining_weight_grams() const
{
    return std::max(0, kGarmentCapacityGrams - load_weight_grams());
}

int LaundrySession::effective_max_temperature_c() const
{
    if (level_ == nullptr || loaded_garments() == 0)
        return 0;
    int limit = std::numeric_limits<int>::max();
    for (std::size_t i = 0; i < items_.size(); ++i)
        if (items_[i].loaded)
            limit = std::min<int>(limit, level_->garments[i].max_temperature_c);
    return limit == std::numeric_limits<int>::max() ? 0 : limit;
}

int LaundrySession::effective_max_spin_rpm() const
{
    if (level_ == nullptr || loaded_garments() == 0)
        return 0;
    int limit = std::numeric_limits<int>::max();
    for (std::size_t i = 0; i < items_.size(); ++i)
        if (items_[i].loaded)
            limit = std::min<int>(limit, level_->garments[i].max_spin_rpm);
    return limit == std::numeric_limits<int>::max() ? 0 : limit;
}

bool LaundrySession::loaded_garments_have_read_labels() const
{
    if (level_ == nullptr || items_.size() != level_->garments.size())
        return false;
    for (const ItemState &item : items_)
        if (item.loaded && !item.label_read)
            return false;
    return true;
}

StartBlock LaundrySession::start_block() const
{
    if (animation_.phase != CyclePhase::idle)
        return StartBlock::cycle_already_started;
    if (level_ == nullptr || loaded_garments() == 0)
        return StartBlock::empty_drum;
    if (door_open_)
        return StartBlock::door_open;
    if (!loaded_garments_have_read_labels())
        return StartBlock::unread_labels;
    if (load_weight_grams() > kGarmentCapacityGrams)
        return StartBlock::capacity_exceeded;
    if (!machine_.program_selected || !machine_.temperature_selected || !machine_.spin_selected ||
        !machine_.detergent_selected || !machine_.softener_selected || !machine_.additive_selected)
        return StartBlock::missing_settings;
    return StartBlock::none;
}

bool LaundrySession::start_cycle()
{
    if (start_block() != StartBlock::none)
        return false;
    animation_ = {};
    animation_.phase = CyclePhase::filling;
    return true;
}

bool LaundrySession::advance_cycle(float dt)
{
    if (animation_.phase == CyclePhase::idle || animation_.phase == CyclePhase::complete)
        return false;
    const float step = std::clamp(dt, 0.0f, 0.2f);
    animation_.cycle_seconds = std::min(kTotalCycleSeconds, animation_.cycle_seconds + step);
    const float time = animation_.cycle_seconds;
    animation_.drum_angle = std::fmod(animation_.drum_angle, 6.2831853f);
    if (time < kFillSeconds)
    {
        animation_.phase = CyclePhase::filling;
        animation_.phase_seconds = time;
        const float t = time / kFillSeconds;
        animation_.water_level = 0.43f * smooth(t);
        animation_.drum_angle += std::sin(time * 2.5f) * step * 0.16f;
        animation_.garment_sway = std::sin(time * 3.0f) * 0.18f;
        animation_.foam = 0.0f;
    }
    else if (time < kFillSeconds + kWashSeconds)
    {
        animation_.phase = CyclePhase::washing;
        animation_.phase_seconds = time - kFillSeconds;
        const float t = animation_.phase_seconds;
        animation_.water_level = 0.43f + std::sin(t * 2.1f) * 0.025f;
        animation_.drum_angle += std::sin(t * 2.7f) * step * 1.35f;
        animation_.garment_sway = std::sin(t * 3.8f) * 0.72f;
        animation_.foam = 0.58f + std::sin(t * 1.3f) * 0.08f;
    }
    else if (time < kFillSeconds + kWashSeconds + kRinseSeconds)
    {
        animation_.phase = CyclePhase::rinsing;
        animation_.phase_seconds = time - kFillSeconds - kWashSeconds;
        const float t = animation_.phase_seconds / kRinseSeconds;
        animation_.water_level = t < 0.32f ? 0.43f + 0.13f * smooth(t / 0.32f)
                                           : 0.56f * (1.0f - smooth((t - 0.32f) / 0.68f));
        animation_.drum_angle += std::sin(animation_.phase_seconds * 2.4f) * step * 0.9f;
        animation_.garment_sway = std::sin(animation_.phase_seconds * 3.0f) * 0.48f;
        animation_.foam = 0.5f * (1.0f - smooth(t));
    }
    else
    {
        animation_.phase = CyclePhase::spinning;
        animation_.phase_seconds = time - kFillSeconds - kWashSeconds - kRinseSeconds;
        const float t = animation_.phase_seconds / kSpinSeconds;
        animation_.water_level = 0.12f * (1.0f - smooth(t));
        const int rpm = std::max(0, machine_.spin_rpm);
        const float max_rate = std::min(22.0f, 5.0f + static_cast<float>(rpm) * 0.012f);
        animation_.spin_rate = max_rate * smooth(t);
        animation_.drum_angle += animation_.spin_rate * step;
        animation_.garment_sway = std::sin(animation_.drum_angle * 2.0f) * 0.2f * (1.0f - t);
        animation_.foam = 0.0f;
    }
    if (animation_.cycle_seconds >= kTotalCycleSeconds)
    {
        animation_.phase = CyclePhase::complete;
        animation_.phase_seconds = 0.0f;
        animation_.water_level = 0.0f;
        animation_.spin_rate = 0.0f;
        animation_.foam = 0.0f;
        animation_.garment_sway = 0.0f;
        return true;
    }
    return false;
}

Evaluation LaundrySession::evaluate() const
{
    Evaluation result;
    result.score = 300;
    if (level_ == nullptr)
    {
        result.score = 0;
        result.stars = 0;
        return result;
    }
    for (std::size_t i = 0; i < level_->garments.size() && i < items_.size(); ++i)
    {
        const GarmentDefinition &garment = level_->garments[i];
        const ItemState &state = items_[i];
        if (state.loaded && !garment.valid_for_level)
        {
            const std::string reason = garment.reason.empty() ? "No pertenece a esta colada." :
                                                                 std::string(garment.reason);
            penalize(result, 28, std::string(garment.name) + ": " + reason);
        }
        if (!state.loaded && garment.valid_for_level)
            penalize(result, 16, std::string("Falta lavar: ") + std::string(garment.name) + ".");
        if (!state.loaded)
            continue;
        if (!garment.machine_washable)
            penalize(result, 55, std::string(garment.name) + " no admite lavado a máquina.");
        if (!program_safe_for(garment, machine_.program))
            penalize(result, 24, std::string("El programa elegido no es seguro para ") +
                                     std::string(garment.name) + ".");
        if (!detergent_safe_for(garment, machine_.detergent))
            penalize(result, 18, std::string(detergent_name(machine_.detergent)) +
                                     " no es compatible con " + std::string(garment.name) + ".");
        if (garment.needs_mesh && !state.in_mesh)
            penalize(result, 20, std::string(garment.name) + " necesita bolsa de malla.");
        if (garment.stain != Stain::none && state.treatment != treatment_for(garment.stain))
            penalize(result, 18, std::string(garment.name) + " requiere " +
                                     std::string(treatment_name(treatment_for(garment.stain))) + ".");
        if (garment.stain == Stain::none && state.treatment != Treatment::none)
            penalize(result, 8, std::string(garment.name) + " no necesitaba pretratamiento.");
    }

    const int maximum_temperature = effective_max_temperature_c();
    const int maximum_spin = effective_max_spin_rpm();
    const int safe_temperature = std::min(maximum_temperature,
                                          program_temperature_limit(machine_.program));
    const int safe_spin = std::min(maximum_spin, program_spin_limit(machine_.program));
    const int target_temperature = std::min<int>(level_->recommended_temperature_c,
                                                  std::max(0, safe_temperature));
    const int target_spin = std::min<int>(level_->recommended_spin_rpm, std::max(0, safe_spin));

    if (machine_.program != level_->recommended_program)
        penalize(result, 20, "El programa no corresponde a la colada.");
    if (machine_.temperature_c > safe_temperature)
        penalize(result, 38, "La temperatura supera el máximo de la etiqueta más delicada.");
    else if (machine_.temperature_c < target_temperature)
        penalize(result, 8, "La temperatura quedó por debajo del objetivo de lavado.");
    if (machine_.spin_rpm > safe_spin)
        penalize(result, 30, "El centrifugado supera el máximo permitido por las etiquetas.");
    else if (machine_.spin_rpm < target_spin)
        penalize(result, 7, "El centrifugado quedó por debajo del objetivo de la colada.");

    if (machine_.detergent != level_->recommended_detergent)
        penalize(result, 18, "El detergente elegido no es el adecuado para esta misión.");
    if (level_->recommended_softener != Softener::any &&
        machine_.softener != level_->recommended_softener)
        penalize(result, 12, "El suavizante no coincide con las necesidades de la carga.");
    if (machine_.additive != level_->recommended_additive)
        penalize(result, 16, "El aditivo elegido no coincide con el tratamiento requerido.");

    for (std::size_t i = 0; i < level_->garments.size() && i < items_.size(); ++i)
    {
        if (!items_[i].loaded)
            continue;
        if (!additive_safe_for(level_->garments[i], machine_.additive))
        {
            penalize(result, machine_.additive == Additive::chlorine_bleach ? 34 : 22,
                     std::string(additive_name(machine_.additive)) + " no es seguro para " +
                         std::string(level_->garments[i].name) + ".");
        }
        if (machine_.softener != Softener::none &&
            (level_->garments[i].fabric == Fabric::sport ||
             level_->garments[i].fabric == Fabric::down ||
             level_->garments[i].fabric == Fabric::wool ||
             level_->garments[i].fabric == Fabric::silk ||
             level_->garments[i].fabric == Fabric::delicate))
            penalize(result, 20, "Evita el suavizante en tejidos deportivos, acolchados o delicados.");
        if (machine_.softener == Softener::standard && level_->garments[i].baby_sensitive)
            penalize(result, 18, "La ropa de bebé requiere un suavizante hipoalergénico o ninguno.");
    }
    if (machine_.additive == Additive::color_protect &&
        !load_has_mixed_color(*level_, items_))
        penalize(result, 6, "La toallita atrapacolor no era necesaria en esta carga.");
    result.score = std::clamp(result.score, 0, 300);
    result.stars = result.score >= 270 ? 3 : result.score >= 205 ? 2 : 1;
    result.perfect = result.feedback.empty();
    if (result.perfect)
        result.feedback.emplace_back("Lavado perfecto: clasificación, etiquetas y productos correctos.");
    return result;
}

std::string_view program_name(Program value)
{
    switch (value)
    {
    case Program::unselected: return "Por elegir";
    case Program::cotton: return "Algodón / Estándar";
    case Program::synthetics: return "Sintéticos / Mixto";
    case Program::delicates: return "Delicados";
    case Program::wool: return "Lana / Lavado a mano";
    case Program::sport: return "Ropa deportiva";
    case Program::quick: return "Rápido 15 / 30 min";
    case Program::eco: return "Eco 40-60";
    }
    return "Programa";
}

std::string_view detergent_name(Detergent value)
{
    switch (value)
    {
    case Detergent::unselected: return "Por elegir";
    case Detergent::none: return "Sin detergente";
    case Detergent::universal: return "Universal";
    case Detergent::color: return "Ropa de color";
    case Detergent::wool: return "Lana y seda";
    case Detergent::sport: return "Ropa deportiva";
    case Detergent::eco: return "Eco gel";
    }
    return "Detergente";
}

std::string_view softener_name(Softener value)
{
    switch (value)
    {
    case Softener::unselected: return "Por elegir";
    case Softener::none: return "Sin suavizante";
    case Softener::standard: return "Suavizante estándar";
    case Softener::hypoallergenic: return "Hipoalergénico";
    case Softener::any: return "Cualquiera";
    }
    return "Suavizante";
}

std::string_view additive_name(Additive value)
{
    switch (value)
    {
    case Additive::unselected: return "Por elegir";
    case Additive::none: return "Ninguno";
    case Additive::oxygen_bleach: return "Lejía de oxígeno activo";
    case Additive::color_protect: return "Atrapacolor";
    case Additive::chlorine_bleach: return "Lejía con cloro";
    }
    return "Aditivo";
}

std::string_view treatment_name(Treatment value)
{
    switch (value)
    {
    case Treatment::none: return "ningún tratamiento";
    case Treatment::grease_remover: return "quitagrasas enzimático";
    case Treatment::cold_enzyme: return "enzimático con agua fría";
    case Treatment::brush_prewash: return "cepillado y prelavado";
    case Treatment::oxygen_spotter: return "quitamanchas de oxígeno";
    }
    return "tratamiento";
}

std::string_view fabric_name(Fabric value)
{
    switch (value)
    {
    case Fabric::cotton: return "Algodón";
    case Fabric::denim: return "Tejano";
    case Fabric::synthetic: return "Sintético";
    case Fabric::wool: return "Lana";
    case Fabric::silk: return "Seda";
    case Fabric::delicate: return "Encaje delicado";
    case Fabric::sport: return "Microfibra deportiva";
    case Fabric::down: return "Acolchado";
    case Fabric::leather: return "Cuero";
    }
    return "Tejido";
}

std::string_view color_name(TextileColor value)
{
    switch (value)
    {
    case TextileColor::white: return "Blanco";
    case TextileColor::dark: return "Oscuro";
    case TextileColor::color: return "Color";
    }
    return "Color";
}

std::string_view stain_name(Stain value)
{
    switch (value)
    {
    case Stain::none: return "Sin mancha";
    case Stain::oil: return "Grasa o aceite";
    case Stain::blood: return "Sangre";
    case Stain::mud: return "Barro";
    case Stain::wine: return "Fruta o vino";
    }
    return "Mancha";
}

std::string_view cycle_phase_name(CyclePhase value)
{
    switch (value)
    {
    case CyclePhase::idle: return "Preparación";
    case CyclePhase::filling: return "Llenado";
    case CyclePhase::washing: return "Lavado";
    case CyclePhase::rinsing: return "Aclarado";
    case CyclePhase::spinning: return "Centrifugado";
    case CyclePhase::complete: return "Ciclo terminado";
    }
    return "Ciclo";
}

std::string_view start_block_message(StartBlock value)
{
    switch (value)
    {
    case StartBlock::none: return "Todo preparado para iniciar.";
    case StartBlock::empty_drum: return "Carga al menos una prenda en el tambor.";
    case StartBlock::door_open: return "Cierra la puerta antes de iniciar.";
    case StartBlock::unread_labels: return "Lee la etiqueta de cada prenda que vas a lavar.";
    case StartBlock::missing_settings:
        return "Elige programa, temperatura, centrifugado y cada producto; «ninguno» también cuenta.";
    case StartBlock::capacity_exceeded: return "La carga supera los 6 kg disponibles para prendas.";
    case StartBlock::cycle_already_started:
        return "El ciclo ya ha comenzado o terminó. Reinicia el nivel para iniciar otro.";
    }
    return "Revisa la preparación de la lavadora.";
}

} // namespace hui::game
