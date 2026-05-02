import { useQuery, useQueries } from '@tanstack/react-query';
import { fetchUserProfile, fetchTests, fetchUserAnswers, fetchMaterials } from '../api/api';

export const useUserProfile = () => {
  return useQuery({
    queryKey: ['userProfile'],
    queryFn: fetchUserProfile,
  });
};

export const useProfileStats = () => {
  const { data: profile, isLoading: profileLoading, error: profileError } = useUserProfile();
  const { data: tests, isLoading: testsLoading } = useQuery({
    queryKey: ['tests'],
    queryFn: fetchTests,
  });
  const { data: materials, isLoading: materialsLoading } = useQuery({
    queryKey: ['materials'],
    queryFn: fetchMaterials,
  });

  const answersQueries = useQueries({
    queries: (tests || []).map(test => ({
      queryKey: ['userAnswers', test.id],
      queryFn: () => fetchUserAnswers(test.id),
    })),
  });

  const isLoading = profileLoading || testsLoading || materialsLoading || answersQueries.some(q => q.isLoading);
  const error = profileError || answersQueries.find(q => q.error)?.error;

  const stats = (() => {
    if (!tests || !answersQueries.length) return {};
    let completedTests = 0;
    let totalScoreSum = 0;
    let testsWithScore = 0;
    answersQueries.forEach((res, idx) => {
      const answers = res.data;
      if (answers?.length) {
        completedTests++;
        const userScore = answers.reduce((sum, ans) => sum + (ans.score || 0), 0);
        const maxScore = tests[idx].max_score;
        if (maxScore) {
          totalScoreSum += (userScore / maxScore) * 100;
          testsWithScore++;
        }
      }
    });
    const averageScore = testsWithScore ? Math.round(totalScoreSum / testsWithScore) : 0;
    const overallProgress = tests.length ? Math.round((completedTests / tests.length) * 100) : 0;
    return {
      totalMaterials: materials?.length || 0,
      totalTests: tests.length,
      completedTests,
      averageScore,
      overallProgress,
    };
  })();

  return { profile, stats, isLoading, error };
};