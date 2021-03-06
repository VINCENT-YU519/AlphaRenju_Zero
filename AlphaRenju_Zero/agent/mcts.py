from .node import Node
import numpy as np
from ..rules import *


class MCTS:
    def __init__(self, conf, net, color):
        """Hyperparameters"""
        self._c_puct = conf['c_puct']  # PUCT
        self._simulation_times = conf['simulation_times']  # number of simulation
        self._tau = conf['initial_tau']  # temperature parameter
        self._careful_stage = conf['careful_stage']  # the stage after which we set tau to zero
        self._epsilon = conf['epsilon']  # proportion of dirichlet noise
        self._dirichlet = conf['dirichlet']
        self._board_size = conf['board_size']
        self._color = color  # MCTS Agent's color ( 1 for black; -1 for white)
        """Monte Carlo Tree"""
        self._root = Node(1.0, None, BLACK)
        """Convolutional Residual Neural Network"""
        self._network = net
        self._is_self_play = conf['is_self_play']

    def set_self_play(self, is_self_play):
        self._is_self_play = is_self_play

    def reset(self):
        self._root = Node(1.0, None, BLACK)
    
    def action(self, board, last_action, stage):  # Note that this function is open to the environment.
        """Adjust the Root Node corresponding to the latest enemy action"""

        # the root corresponds to the last board = board - last_action
        if self._root.is_leaf():
            last_board = np.copy(board)
            if last_action is not None:
                row, col = last_action[0], last_action[1]
                last_board[row][col] = 0
            self._simulate(last_board)

        # now move the root to the child corresponding to the board
        if last_action is not None:
            last_action_ind = coordinate2index(last_action, self._board_size)
            self._root = self._root.children()[last_action_ind]

        # must check whether the root is a leaf node before prediction
        pi = self._predict(board)
        """Action Decision"""
        if stage <= self._careful_stage:  # Uncareful Stage where optimal action may not be taken
            position_list = [i for i in range(self._board_size * self._board_size)]
            action = np.random.choice(position_list, p=pi)
        else:  # Careful Stage where we play optimally
            action = np.argmax(pi)
        """Adjust the Root Node and discard the remainder of the tree"""
        if not self._is_self_play:
            self._root = self._root.children()[action]
        return action, pi  # You need to store pi for training use
    
    def _predict(self, board):
        self._simulate(board)
        pi = np.array([(node.N())**(1/self._tau) for node in self._root.children()])
        pi = pi/sum(pi)
        return pi
    
    def _simulate(self, root_board):    # ROOT BOARD MUST CORRESPOND TO THE ROOT NODE!!!
        legal_vec_root = board2legalvec(root_board)
        for epoch in range(self._simulation_times):
            current_node = self._root
            legal_vec_current = np.copy(legal_vec_root)  # deep copy
            current_color = self._root.color
            current_board = np.copy(root_board)
            action = None
            while not current_node.is_leaf():
                current_node, action = current_node.select(self._c_puct, legal_vec_current)
                legal_vec_current[action] = 0
                row, col = index2coordinate(action, self._board_size)
                current_board[row][col] = current_color
                current_color = -current_color
            # now current_node must be a leaf

            if current_node.is_end:
                current_node.backup(-current_node.value)
                continue

            # calculate the prior probabilities and value
            p, v = self._network.predict(current_board, current_color)
            prior_prob = p[0]

            # now check whether this leaf node is an end node
            if action is not None:
                end_flag = check_rules(current_board, action, -current_color)
                if end_flag == 'blackwins' or end_flag == 'whitewins' or end_flag == 'full':
                    current_node.is_end = True
                    current_node.end_reason = end_flag
                    current_node.value = -v
                else:
                    current_node.expand(prior_prob, self._board_size)
            else:
                # if action is None, then the root node is a leaf
                current_node.expand(prior_prob, self._board_size)
            current_node.backup(-v)


def index2coordinate(index, size):
    row = index // size
    col = index % size
    return int(row), int(col)


def coordinate2index(cor, size):
    return size * cor[0] + cor[1]


def board2legalvec(board):
    vec = np.array(np.array(board) == 0, dtype=np.int)
    return vec.flatten()


def check_rules(board, action, color):
    stone_num = sum(sum(np.abs(board)))
    if stone_num <= 8:  # Impossible to end since the maximal length of consecutive lines with the same color is four.
        return 'continue'
    else:
        if stone_num == board.shape[0] * board.shape[0]:
            return 'full'
        else:  # Greedy Match
            cor = index2coordinate(action, board.shape[0])
            # Horizonal Check
            count = 1
            for i in range(1, 5):
                if cor[1] + i <= board.shape[0] - 1:
                    if board[cor[0]][cor[1]+i] == color:
                        count += 1
                    else:
                        break
                else:
                    break
            for i in range(1, 5):
                if cor[1] - i >= 0:
                    if board[cor[0]][cor[1]-i] == color:
                        count += 1
                    else:
                        break
                else:
                    break
            if count >= 5:
                if color == 1:
                    return 'blackwins'
                else:
                    return 'whitewins'
            # Vertical Check
            count = 1
            for i in range(1, 5):
                if cor[0]+i <= board.shape[0]-1:
                    if board[cor[0]+i][cor[1]] == color:
                        count += 1
                    else:
                        break
                else:
                    break
            for i in range(1, 5):
                if cor[0]-i >= 0:
                    if board[cor[0]-i][cor[1]] == color:
                        count += 1
                    else:
                        break
                else:
                    break
            if count >= 5:
                if color == 1:
                    return 'blackwins'
                else:
                    return 'whitewins'
            # Diagonal Check
            count = 1
            for i in range(1, 5):
                if (cor[0]+i <= board.shape[0]-1) and (cor[1]+i <= board.shape[0]-1):
                    if board[cor[0]+i][cor[1]+i] == color:
                        count += 1
                    else:
                        break
                else:
                    break
            for i in range(1, 5):
                if (cor[0]-i >= 0) and (cor[1]-i >= 0):
                    if board[cor[0]-i][cor[1]-i] == color:
                        count += 1
                    else:
                        break
                else:
                    break
            if count >= 5:
                if color == 1:
                    return 'blackwins'
                else:
                    return 'whitewins'
            # Anti-Diagonal Check
            count = 1
            for i in range(1, 5):
                if (cor[0]+i <= board.shape[0]-1) and (cor[1]-i >= 0):
                    if board[cor[0]+i][cor[1]-i] == color:
                        count += 1
                    else:
                        break
                else:
                    break
            for i in range(1, 5):
                if (cor[0]-i >= 0) and (cor[1]+i <= board.shape[0]-1):
                    if board[cor[0]-i][cor[1]+i] == color:
                        count += 1
                    else:
                        break
                else:
                    break
            if count >= 5:
                if color == 1:
                    return 'blackwins'
                else:
                    return 'whitewins'





'''
    else: # Convolutional Match
        kernel = color*np.ones(5)
        # Horizonal Convolution
        # (i,j) is the coordinate of the starting point
        for i in range(board.shape[0]):
            for j in range(board.shape[0]-5+1):
                sample = board[i,j:j+5]
                result = np.dot(kernel,sample)
                if result == 5:
                    if color == 1:
                        return 'blackwins'
                    else:
                        return 'whitewins'
                else:
                    continue
        # Vertical Convolution
        for i in range(board.shape[0]-5+1):
            for j in range(board.shape[0]):
                sample = board[i:i+5,j]
                result = np.dot(kernel,sample)
                if result == 5:
                    if color == 1:
                        return 'blackwins'
                    else:
                        return 'whitewins'
                else:
                    continue     
        # Diagonal Convolution
        for i in range(board.shape[0]-5+1):
            for j in range(board.shape[0]-5+1):
                sample = np.array([ board[i+k][j+k] for k in range(5)])
                result = np.dot(kernel,sample)
                if result == 5:
                    if color == 1:
                        return 'blackwins'
                    else:
                        return 'whitewins'
                else:
                    continue
        # Anti-Diagonal Convolution
        for i in range(board.shape[0]-5+1):
            for j in range(board.shape[0]-5+1,board.shape[0]):
                sample = np.array([ board[i+k][j-k] for k in range(5)])
                result = np.dot(kernel,sample)
                if result == 5:
                    if color == 1:
                        return 'blackwins'
                    else:
                        return 'whitewins'
                else:
                    continue
    return 'continue'    

'''