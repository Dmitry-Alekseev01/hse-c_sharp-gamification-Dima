import { useMutation, useQueryClient } from '@tanstack/react-query';
import { submitAnswer, completeTestAttempt } from '../api/api';

export const useSubmitTest = (testId, attemptId) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (answers) => {
      for (const ans of answers) {
        await submitAnswer(testId, ans.questionId, ans.payload, attemptId);
      }
      await completeTestAttempt(attemptId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tests'] });
      queryClient.invalidateQueries({ queryKey: ['userScores'] });
      queryClient.invalidateQueries({ queryKey: ['userProgress'] });
    },
  });
};
