import { useQuery } from '@tanstack/react-query';
import { fetchTests, fetchUserAnswers, fetchTestContent } from '../api/api';

export const useTests = () => {
  return useQuery({
    queryKey: ['tests'],
    queryFn: fetchTests,
  });
};

export const useUserScores = (tests) => {
  return useQuery({
    queryKey: ['userScores', tests?.map((t) => t.id)],
    queryFn: async () => {
      if (!tests) return {};
      const scoresMap = {};
      await Promise.all(
        tests.map(async (test) => {
          try {
            const answers = await fetchUserAnswers(test.id);
            if (answers?.length) {
              const userScore = answers.reduce((sum, ans) => sum + (ans.score || 0), 0);
              scoresMap[test.id] = { userScore, maxScore: test.max_score };
            }
          } catch (e) {}
        })
      );
      return scoresMap;
    },
    enabled: !!tests,
    staleTime: 2 * 60 * 1000,
  });
};

export const useQuestionsCount = (tests) => {
  return useQuery({
    queryKey: ['questionsCount', tests?.map((t) => t.id)],
    queryFn: async () => {
      if (!tests) return {};
      const countMap = {};
      await Promise.all(
        tests.map(async (test) => {
          try {
            const content = await fetchTestContent(test.id);
            countMap[test.id] = content.questions.length;
          } catch (err) {}
        })
      );
      return countMap;
    },
    enabled: !!tests,
    staleTime: 10 * 60 * 1000,
  });
};
