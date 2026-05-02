import { useQuery } from '@tanstack/react-query';
import { fetchMaterials, fetchMaterialById } from '../api/api';

export const useMaterials = () => {
  return useQuery({
    queryKey: ['materials'],
    queryFn: fetchMaterials,
  });
};

export const useMaterial = (id) => {
  return useQuery({
    queryKey: ['material', id],
    queryFn: () => fetchMaterialById(id),
    enabled: !!id,
  });
};
