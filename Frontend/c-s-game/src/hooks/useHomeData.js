import { useQuery } from '@tanstack/react-query';
import { fetchUserProfile, fetchUserProgress, fetchTests, fetchMaterials, fetchLevels } from '../api/api';

export const useUserProfile = () => {
  return useQuery({
    queryKey: ['userProfile'],
    queryFn: fetchUserProfile,
  });
};

export const useUserProgress = (userId) => {
  return useQuery({
    queryKey: ['userProgress', userId],
    queryFn: () => fetchUserProgress(userId),
    enabled: !!userId,
  });
};

export const useTests = () => {
  return useQuery({
    queryKey: ['tests'],
    queryFn: fetchTests,
  });
};

export const useMaterials = () => {
  return useQuery({
    queryKey: ['materials'],
    queryFn: fetchMaterials,
  });
};

export const useLevels = () => {
  return useQuery({
    queryKey: ['levels'],
    queryFn: fetchLevels,
  });
};