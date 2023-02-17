import numpy as np
from random import randrange

class FixedSequence():
    pass

class UserSelected():
    pass


class EpsilonGreedy:
    def __init__(self, num_arms, epsilon=0.2):
        self.num_arms = num_arms
        self.epsilon = epsilon
        self.sum_rewards = np.zeros(self.num_arms)
        self.num_pulls = np.zeros(self.num_arms)
        self.t = 1

    def get_arm(self):
        for idx, num_pull in enumerate(self.num_pulls):
            if num_pull == 0:
                pulled_arm = idx
                self.t += 1
                return pulled_arm 

        if np.random.binomial(n = 1, p = self.epsilon) == 1:
            self.t += 1
            return randrange(self.num_arms) # randomly generate integers in between 0 and self.num_arms
        else:
            pulled_arm = np.argmax(self.sum_rewards / self.num_pulls)
            self.t += 1
            return pulled_arm

    def update_arm(self, arm, reward):
        self.sum_rewards[arm] += reward   
        self.num_pulls[arm] += 1


class ExploreThenCommit:
    def __init__(self, num_arms, T_total = 50, c = .5):
        self.num_arms = num_arms
        self.T_explore_per_arm = int(c * int(T_total ** (2/3)))
        self.T_explore = self.T_explore_per_arm * num_arms
        self.sum_rewards = np.zeros(self.num_arms)
        self.num_pulls = np.zeros(self.num_arms)
        self.t = 1

    def get_arm(self):
        if self.t in range(1, self.T_explore + 1): # t: 1 ~ self.T_explore
            pulled_arm = (self.t-1) % self.num_arms  # arm is 0 ~ (K-1)
            self.t += 1
            return pulled_arm
        else:
            pulled_arm = np.argmax(self.sum_rewards / self.num_pulls)
            self.t += 1
            return pulled_arm

    def update_arm(self, arm, reward):
        self.sum_rewards[arm] += reward   
        self.num_pulls[arm] += 1


class TS:
    ## we use dirichlet distribution as a prior
    ## dirichlet - multinomial 

    def __init__(self, num_arms, categories = 9):
        self.num_arms = num_arms
        self.categories = categories
        #right now, we are just assuming the prior will be 1/categories
        self.alphas = np.array([[1] * self.categories] * self.num_arms)

    def _one_hot_encode(self, reward): # reward will be 1~categories and discrete
        one_hot = np.zeros(self.categories)
        one_hot[reward - 1] = 1
        return one_hot

    def _one_hot_decode(self, one_hot):
        for i in range(one_hot.shape[0]):
            if one_hot[i] == 1:
                return (i + 1) # since i only ranges from 0 ~like_categories

    def get_arm(self):
        virtual_rewards = [None] * self.num_arms
        for arm in range(self.num_arms):
            p = np.random.dirichlet(self.alphas[arm])
            #print (arm, p)
            one_hot_reward = np.random.multinomial(1, p) # returns a one hot encoded reward
            virtual_rewards[arm] = self._one_hot_decode(one_hot_reward)
        #print (virtual_rewards)
        return np.argmax(virtual_rewards)

    def update_arm(self, arm, reward):
        # update the distribution
        one_hot_reward = self._one_hot_encode(reward)
        self.alphas[arm] = self.alphas[arm] + one_hot_reward 


class UCB:
    def __init__(self, num_arms, alpha=2.0):
        self.num_arms = num_arms
        self.alpha = alpha
        self.sum_rewards = np.zeros(self.num_arms)
        self.num_pulls = np.zeros(self.num_arms)
        self.t = 1
        
    def _get_ucb(self):
        ucb =  self.sum_rewards / self.num_pulls + np.sqrt(self.alpha * np.log(self.t) / self.num_pulls)
        return ucb

    def get_arm(self):
        for idx, num_pull in enumerate(self.num_pulls):
            if num_pull == 0:
                pulled_arm = idx
                self.t += 1
                return pulled_arm 
            
        ucbs = self._get_ucb()
        pulled_arm = np.argmax(ucbs)
        self.t += 1
        return pulled_arm
    
    def update_arm(self, arm, reward):
        self.sum_rewards[arm] += reward   
        self.num_pulls[arm] += 1
