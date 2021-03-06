from . import *
from .dataset.dataset import *


class Env:
    def __init__(self, conf):
        self._conf = conf
        self._is_self_play = conf['is_self_play']

        self._rules = Rules(conf)
        self._renderer = Renderer(conf['screen_size'], conf['board_size'])
        self._board = Board(self._renderer, conf['board_size'])

        self._agent_1 = MCTSAgent(conf, color=BLACK)
        # self._agent_1 = HumanAgent(self._renderer, color=BLACK)
        # self._agent_2 = HumanAgent(self._renderer, color=WHITE)
        self._agent_2 = MCTSAgent(conf, color=WHITE)
        self._agent_eval = MCTSAgent(conf, color=WHITE)
        self._agent_eval.set_self_play(False)

        if self._is_self_play:
            self._agent_2 = self._agent_1

        self._epoch = conf['epoch']
        self._sample_percentage = conf['sample_percentage']
        self._games_num = conf['games_num']
        self._evaluate_games_num = conf['evaluate_games_num']

    def run(self, record=None):
        result = None
        while self._renderer.is_alive():
            if self._is_self_play:
                self._agent_1.color = self._board.current_player()
            action, pi = self._current_agent().play(self._obs(), self._board.last_move(), self._board.stone_num())
            result = self._check_rules(action)
            if result == 'continue':
                color = self._board.current_player()
                # print(result + ': ', action, color)
                self._board.move(color, action)
                if record is not None and pi is not None:
                    obs = self._board.board()
                    record.add(obs, color, pi)
            if result == 'occupied':
                print(result + ': ' + str(action))
                continue
            if result == 'blackwins' or result == 'whitewins' or result == 'draw':
                self._board.move(self._board.current_player(), action)
                print(result)
                color = self._board.current_player()
                self._board.move(color, action)
                if record is not None and pi is not None:
                    obs = self._board.board()
                    record.add(obs, color, pi)
                    if result == 'blackwins':
                        flag = 1
                    if result == 'whitewins':
                        flag = -1
                    if result == 'draw':
                        flag = 0
                    record.set_z(flag)
                # time.sleep(30)
                break
        self._board.clear()
        self._agent_1.reset_mcts()
        self._agent_2.reset_mcts()
        print('*****************************************************')
        if result == 'blackwins':
            return BLACK
        if result == 'whitewins':
            return WHITE
        return 0

    def train(self):
        for epoch in range(self._epoch):
            data_set = DataSet()
            print('epoch = ' + str(epoch))
            for i in range(self._games_num):
                record = GameRecord()
                print('game_num = ' + str(i))
                self.run(record)
                data_set.add_record(record)
            obs, col, pi, z = data_set.get_sample(self._sample_percentage)
            self._agent_1.train(obs, col, pi, z)

            # ready to evaluate
            if self.evaluate():
                self._agent_1.save_model()
            print('*****************************************************')

    def evaluate(self):
        print('Evaluation begins:')

        # switch mode
        self._is_self_play = False
        self._agent_1.set_self_play(False)
        self._agent_2 = self._agent_eval
        self._agent_2.load_model()

        new_model_wins_num = 0
        total_num = self._evaluate_games_num

        for i in range(int(total_num/2)):
            new_model_wins_num += max(self.run(), 0)   # new model plays BLACK
            print('number of new model wins: ' + str(new_model_wins_num) + '/' + str(i+1))

        # switch agents
        self._agent_1, self._agent_2 = self._agent_2, self._agent_1
        self._agent_1.color = BLACK
        self._agent_2.color = WHITE

        for i in range(int(total_num/2)):
            new_model_wins_num -= min(self.run(), 0)
            print('number of new model wins: ' + str(new_model_wins_num) + '/' + str(i+1+int(total_num/2)))

        # so far self._agent_1 -> self._agent_eval

        self._agent_1 = self._agent_2
        self._agent_1.color = BLACK
        self._agent_1.set_self_play(True)
        self._is_self_play = True

        rate = new_model_wins_num / total_num
        print('winning rate = ' + str(rate))
        if rate > 0.55:
            print('adopt new model')
            return True
        else:
            print('discard new model')
            return False

    def _obs(self):
        return self._board.board()

    def _current_agent(self):
        if self._board.current_player() == BLACK:
            return self._agent_1
        else:
            return self._agent_2

    def _check_rules(self, action):
        return self._rules.check_rules(self._board.board(), action, self._board.current_player())
