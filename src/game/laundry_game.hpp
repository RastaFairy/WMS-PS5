// Maestro Lavandero: native 2D washing-learning game model.
// Copyright (C) 2026 BlackBearReloaded
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace hui::game
{

constexpr std::size_t kLevelCount = 20;
constexpr int kWasherCapacityGrams = 8000;
constexpr int kCycleWaterGrams = 2000;
constexpr int kGarmentCapacityGrams = kWasherCapacityGrams - kCycleWaterGrams;

enum class Program : std::uint8_t
{
    unselected,
    cotton,
    synthetics,
    delicates,
    wool,
    sport,
    quick,
    eco,
};

enum class Detergent : std::uint8_t
{
    unselected,
    none,
    universal,
    color,
    wool,
    sport,
    eco,
};

enum class Softener : std::uint8_t
{
    unselected,
    none,
    standard,
    hypoallergenic,
    any,
};

enum class Additive : std::uint8_t
{
    unselected,
    none,
    oxygen_bleach,
    color_protect,
    chlorine_bleach,
};

enum class Treatment : std::uint8_t
{
    none,
    grease_remover,
    cold_enzyme,
    brush_prewash,
    oxygen_spotter,
};

enum class Fabric : std::uint8_t
{
    cotton,
    denim,
    synthetic,
    wool,
    silk,
    delicate,
    sport,
    down,
    leather,
};

enum class TextileColor : std::uint8_t
{
    white,
    dark,
    color,
};

enum class GarmentShape : std::uint8_t
{
    top,
    shirt,
    polo,
    hoodie,
    trousers,
    jeans,
    shorts,
    skirt,
    dress,
    knitwear,
    coat,
    blazer,
    linen,
    towel,
    robe,
    scarf,
    hat,
    belt,
    lingerie,
    bra,
    socks,
    hosiery,
    bib,
    handkerchief,
    romper,
    pajamas,
    tracksuit,
    small_item,
};

enum class Stain : std::uint8_t
{
    none,
    oil,
    blood,
    mud,
    wine,
};

enum class BleachAllowance : std::uint8_t
{
    none,
    oxygen_only,
    any,
};

struct GarmentDefinition
{
    std::string_view id;
    std::string_view name;
    std::string_view reason;
    std::string_view composition;
    Fabric fabric = Fabric::cotton;
    TextileColor color = TextileColor::white;
    GarmentShape shape = GarmentShape::top;
    Stain stain = Stain::none;
    BleachAllowance bleach = BleachAllowance::none;
    std::uint16_t weight_grams = 0;
    std::uint16_t max_temperature_c = 0;
    std::uint16_t max_spin_rpm = 0;
    bool valid_for_level = false;
    bool machine_washable = true;
    bool needs_mesh = false;
    bool eco_compatible = false;
    bool lightly_used = false;
    bool baby_sensitive = false;
};

struct LevelDefinition
{
    std::uint8_t number = 0;
    std::string_view phase;
    std::string_view title;
    std::string_view objective;
    Program recommended_program = Program::cotton;
    std::uint16_t recommended_temperature_c = 0;
    std::uint16_t recommended_spin_rpm = 0;
    Detergent recommended_detergent = Detergent::universal;
    Additive recommended_additive = Additive::none;
    Softener recommended_softener = Softener::none;
    std::vector<GarmentDefinition> garments;
};

std::span<const LevelDefinition> level_catalog();

struct ItemState
{
    bool label_read = false;
    bool loaded = false;
    bool in_mesh = false;
    Treatment treatment = Treatment::none;
};

struct MachineSettings
{
    Program program = Program::unselected;
    int temperature_c = -1;
    int spin_rpm = -1;
    Detergent detergent = Detergent::unselected;
    Softener softener = Softener::unselected;
    Additive additive = Additive::unselected;
    bool program_selected = false;
    bool temperature_selected = false;
    bool spin_selected = false;
    bool detergent_selected = false;
    bool softener_selected = false;
    bool additive_selected = false;
};

enum class CyclePhase : std::uint8_t
{
    idle,
    filling,
    washing,
    rinsing,
    spinning,
    complete,
};

struct CycleAnimation
{
    CyclePhase phase = CyclePhase::idle;
    float phase_seconds = 0.0f;
    float water_level = 0.0f;
    float drum_angle = 0.0f;
    float spin_rate = 0.0f;
    float foam = 0.0f;
    float garment_sway = 0.0f;
    float cycle_seconds = 0.0f;
};

enum class MoveResult : std::uint8_t
{
    loaded,
    unloaded,
    invalid_item,
    door_closed,
    label_not_read,
    capacity_exceeded,
};

enum class StartBlock : std::uint8_t
{
    none,
    empty_drum,
    door_open,
    unread_labels,
    missing_settings,
    capacity_exceeded,
    cycle_already_started,
};

struct Evaluation
{
    int score = 0;
    int stars = 0;
    std::vector<std::string> feedback;
    bool perfect = false;
};

struct PersistentProgress
{
    std::uint8_t unlocked_through = 0;
    std::uint32_t completed_mask = 0;
    std::array<std::uint16_t, kLevelCount> best_scores{};
    std::array<std::uint8_t, kLevelCount> best_stars{};

    int total_best_score() const;
    void record(std::size_t level_index, const Evaluation &evaluation);
};

PersistentProgress load_progress(std::string_view save_root);
bool save_progress(std::string_view save_root, const PersistentProgress &progress);

class LaundrySession
{
  public:
    void begin_level(std::size_t index);

    const LevelDefinition &level() const;
    std::size_t level_index() const;
    const std::vector<ItemState> &items() const;
    ItemState *item_state(std::size_t index);
    const ItemState *item_state(std::size_t index) const;
    MachineSettings &machine_settings();
    const MachineSettings &machine_settings() const;
    CycleAnimation &animation();
    const CycleAnimation &animation() const;

    bool door_open() const;
    void set_door_open(bool open);
    MoveResult move_item(std::size_t index);
    bool mark_label_read(std::size_t index);
    bool toggle_mesh(std::size_t index);
    bool choose_treatment(std::size_t index, Treatment treatment);

    int loaded_garments() const;
    int load_weight_grams() const;
    int remaining_weight_grams() const;
    int effective_max_temperature_c() const;
    int effective_max_spin_rpm() const;
    bool loaded_garments_have_read_labels() const;
    StartBlock start_block() const;
    bool start_cycle();
    bool advance_cycle(float dt);
    Evaluation evaluate() const;

  private:
    const LevelDefinition *level_ = nullptr;
    std::size_t level_index_ = 0;
    std::vector<ItemState> items_;
    MachineSettings machine_;
    CycleAnimation animation_;
    bool door_open_ = true;
};

std::string_view program_name(Program value);
std::string_view detergent_name(Detergent value);
std::string_view softener_name(Softener value);
std::string_view additive_name(Additive value);
std::string_view treatment_name(Treatment value);
std::string_view fabric_name(Fabric value);
std::string_view color_name(TextileColor value);
std::string_view stain_name(Stain value);
std::string_view cycle_phase_name(CyclePhase value);
std::string_view start_block_message(StartBlock value);

} // namespace hui::game
