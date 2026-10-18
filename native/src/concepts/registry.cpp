// Generated registry: exposes the Studio screen as the active UI concept.
#include "concepts/concepts.hpp"
namespace hui::app {
std::span<const ConceptFactory> concept_registry() {
    static constexpr ConceptFactory kFactories[] = { concepts::make_ps5hs_generated };
    return kFactories;
}
} // namespace hui::app