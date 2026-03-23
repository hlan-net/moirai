/**
 * Model capability detection for Moirai
 * Filters models based on tool/function calling support required for agent operations
 */

/**
 * Model patterns that support tool calling
 * Based on Ollama model capabilities
 */
const TOOL_CAPABLE_PATTERNS = [
  /^llama3\./,           // llama3.x models
  /^llama3\.2/,          // llama3.2 specifically
  /^deepseek-r1/,        // DeepSeek R1 reasoning models
  /^deepseek-coder/,     // DeepSeek Coder models
  /^qwen/,               // Qwen models (2.5, 3, etc)
  /^phi4/,               // Phi-4 models
  /^phi3/,               // Phi-3 models
  /^codellama/,          // CodeLlama models
  /^mistral/,            // Mistral models
  /^mixtral/,            // Mixtral models
  /^opencoder/,          // OpenCoder models
  /^granite.*(?<!vision)/, // Granite non-vision models
]

/**
 * Model patterns that do NOT support tool calling
 */
const NO_TOOL_SUPPORT_PATTERNS = [
  /^gemma/,              // Gemma models (1b, 2b, 3, etc)
  /^tinyllama/,          // TinyLlama
  /^tinydolphin/,        // TinyDolphin
  /^llava/,              // Vision models
  /vision/i,             // Any vision model
  /^sqlcoder/,           // SQLCoder (specialized)
  /^embeddinggemma/,     // Embedding models
  /^orca-mini/,          // Orca Mini
  /^smollm/,             // SmolLM
  /^marco-o1/,           // Marco-O1
  /^olmo-3.*think/,      // Olmo thinking models (no tool support)
]

/**
 * Check if a model supports tool/function calling
 */
export function supportsToolCalling(modelName: string): boolean {
  if (!modelName) return false
  
  const lowerName = modelName.toLowerCase()
  
  // Check explicit exclusions first
  for (const pattern of NO_TOOL_SUPPORT_PATTERNS) {
    if (pattern.test(lowerName)) {
      return false
    }
  }
  
  // Check if model matches tool-capable patterns
  for (const pattern of TOOL_CAPABLE_PATTERNS) {
    if (pattern.test(lowerName)) {
      return true
    }
  }
  
  // Default to false (conservative approach - don't show unless confirmed)
  return false
}

/**
 * Filter a list of models to only include tool-capable ones
 */
export function filterToolCapableModels(models: string[]): string[] {
  return models.filter(supportsToolCalling)
}

/**
 * Get a descriptive capability label for a model
 */
export function getModelCapabilityLabel(modelName: string): string {
  if (supportsToolCalling(modelName)) {
    return '✓ Compatible'
  }
  return '✗ No tool support'
}

/**
 * Get recommended models from a list (tool-capable + commonly good)
 */
export function getRecommendedModels(models: string[]): string[] {
  const toolCapable = filterToolCapableModels(models)
  
  // Priority order for recommendations
  const priorities = [
    'llama3.2:3b',
    'llama3.2:latest',
    'llama3.2:1b',
    'deepseek-r1:7b',
    'qwen3:latest',
    'phi4-reasoning:latest',
  ]
  
  const recommended: string[] = []
  
  // Add priority models if they exist
  for (const priority of priorities) {
    if (toolCapable.includes(priority)) {
      recommended.push(priority)
    }
  }
  
  // Add remaining tool-capable models
  for (const model of toolCapable) {
    if (!recommended.includes(model)) {
      recommended.push(model)
    }
  }
  
  return recommended
}
