import { useState, useEffect } from 'react';

export interface OpenRouterModel {
  id: string;
  name: string;
  context_length: number;
}

export function useOpenRouterModels() {
  const [models, setModels] = useState<OpenRouterModel[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchModels() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch('https://openrouter.ai/api/v1/models');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // Sort models alphabetically by name
        const sortedModels = (data.data || []).sort((a: OpenRouterModel, b: OpenRouterModel) => 
          a.name.localeCompare(b.name)
        );
        
        setModels(sortedModels);
      } catch (err: any) {
        console.error('Failed to fetch OpenRouter models:', err);
        setError(err.message || 'Failed to fetch models');
      } finally {
        setIsLoading(false);
      }
    }

    fetchModels();
  }, []);

  return { models, isLoading, error };
}
