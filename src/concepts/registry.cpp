// Only the Taller de Colada main menu is registered in this application.
#include "concepts/concepts.hpp"
namespace hui::app {
std::span<const ConceptFactory> concept_registry() {
    static constexpr ConceptFactory kFactories[] = { concepts::make_taller_menu };
    return kFactories;
}
} // namespace hui::app
