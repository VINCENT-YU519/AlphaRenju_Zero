import pygame
from pygame import *
import time
import threading
from sys import exit
from ..rules import *
import numpy as np

image_path = 'AlphaRenju_Zero/image/'


class Renderer(threading.Thread):

    # Noted that some functions have both public and private versions such as 'move', 'read', 'paint_background'
    # private ones are for Renderer thread, which will finish the rendering while the public func play the role in
    # sending signals to Renderer thread. (by updating some boolean variables, since Renderer Thread is listening
    # these variables in an endless loop)

    # Since all rendering must be done in Renderer thread, we have to take an indirect way.

    def __init__(self, screen_size, board_size=15):
        super(Renderer, self).__init__()
        self._screen_size = screen_size
        self._board_size = board_size
        self._spacing = int(self._screen_size[1] / (board_size + 1))
        self._screen = None
        self._background = None
        self._stone_black = None
        self._stone_white = None

        self._init = False

        self._update_move = False
        self._next_pos = None
        self._next_player = 0

        self._update_read = False
        self._new_board = None

        self._update_clear = False

        self._is_waiting_for_click = False
        self._mouse_click_pos = None

        # 设置后台线程：若是后台线程，在主线程结束之后，后台线程也会停止，若是前台线程，在主线程执行完毕后，等待前台
        # 线程也执行完毕后程序才会停止
        self.setDaemon(True)
        self.start()

    def run(self):
        pygame.init()
        self._screen = pygame.display.set_mode(self._screen_size, 0, 32)
        self._background = pygame.image.load(image_path + 'desk.jpg').convert()
        self._stone_black = pygame.image.load(image_path + 'black.png').convert_alpha()
        self._stone_white = pygame.image.load(image_path + 'white.png').convert_alpha()
        self._stone_black = pygame.transform.smoothscale(self._stone_black, (self._spacing, self._spacing))
        self._stone_white = pygame.transform.smoothscale(self._stone_white, (self._spacing, self._spacing))
        self.paint_background()
        while True:
            for event in pygame.event.get():
                if event.type == QUIT:
                    print("exit")
                    pygame.quit()
                    exit()
                if self._is_waiting_for_click and event.type == MOUSEBUTTONDOWN:
                    mouse_position = mouse.get_pos()
                    y = int(mouse_position[0] / self._spacing - 0.5)
                    x = int(mouse_position[1] / self._spacing - 0.5)
                    if x in range(self._board_size) and y in range(self._board_size):
                        self._is_waiting_for_click = False
                        self._mouse_click_pos = (x, y)
                    print("click" + str(self._mouse_click_pos))
            if self._update_clear:
                self._paint_background()
            if self._update_move:
                self._move(self._next_player, self._next_pos)
            if self._update_read:
                self._read(self._new_board)

    def paint_background(self):
        self._update_clear = True
        self._update_move = False
        self._update_read = False
        self._init = False

    def _paint_background(self):
        self._screen.blit(self._background, (0, 0))

        for i in range(1, self._board_size + 1):
            start_horizontal = (self._spacing, i * self._spacing)
            end_horizontal = (self._screen_size[1] - self._spacing, i * self._spacing)
            start_vertical = (i * self._spacing, self._spacing)
            end_vertical = (i * self._spacing, self._screen_size[1] - self._spacing)

            if i == 1 or i == self._board_size + 1:
                pygame.draw.line(self._screen, (0, 0, 0), start_horizontal, end_horizontal, 3)
                pygame.draw.line(self._screen, (0, 0, 0), start_vertical, end_vertical, 3)
            else:
                pygame.draw.line(self._screen, (0, 0, 0), start_horizontal, end_horizontal, 2)
                pygame.draw.line(self._screen, (0, 0, 0), start_vertical, end_vertical, 2)

        pygame.display.update()
        self._update_clear = False
        self._init = True

    def move(self, player, action):
        while self._update_move:
            time.sleep(.1)
        self._next_player = player
        self._next_pos = action
        self._update_move = True

    def _move(self, player, action):
        position = (int((action[1] + 0.5) * self._spacing), int((action[0] + 0.5) * self._spacing))
        if player == BLACK:
            self._screen.blit(self._stone_black, position)
        elif player == -1:
            self._screen.blit(self._stone_white, position)

        pygame.display.update()
        self._update_move = False

    def read(self, new_board):
        while self._update_read:
            time.sleep(.1)
        self._new_board = new_board
        self._update_read = True

    def _read(self, new_board):
        self._paint_background()
        for row in range(self._board_size):
            for col in range(self._board_size):
                if new_board[row][col] == 1:
                    self._move(1, (row, col))
                elif new_board[row][col] == -1:
                    self._move(-1, (row, col))

        pygame.display.update()
        self._update_read = False

    def ask_for_click(self):
        self._is_waiting_for_click = True
        while self._is_waiting_for_click:
            time.sleep(.01)
        return self._mouse_click_pos

    def show_result(self, result):
        font = pygame.font.SysFont('Calibri', size=50)
        text = font.render(result, True, [255, 255, 0])

    def is_initialized(self):
        return self._init


class Board:
    def __init__(self, renderer, board_size=15):
        self._board = [[0 for i in range(board_size)] for i in range(board_size)]
        self._board_size = board_size
        self._player = BLACK
        self._winner = 0
        self._round = 0
        self._last_move = None

        if renderer is None:
            self._display = False
        else:
            self._display = True
        self._renderer = renderer

    def __str__(self):
        print('round = ' + str(self.round()))
        print('last move = ' + str(self.last_move()))
        if self.current_player() == BLACK:
            return 'current_player = BLACK'
        else:
            return 'current_player = WHITE'

    # return the board
    def board(self):
        return np.copy(self._board)

    # player take an action(coordinate)
    def move(self, player, action):
        x = action[0]   # row
        y = action[1]   # col

        # waiting until renderer is initialized
        while self._display and (not self._renderer.is_initialized()):
            time.sleep(.2)

        if not isinstance(x, int) or not isinstance(y, int):
            print("x, y should be an integer:", x, y)
            return 1, self.board()
        if x < 0 or x > self._board_size - 1 or y < 0 or y > self._board_size - 1:
            print("x, y should be in [0, 14]")
            return 1, self.board()

        if player == BLACK:
            if self._display:
                self._renderer.move(player, (x, y))
            self._board[x][y] = BLACK
            self._player = WHITE
            self._round += 1
        else:
            if self._display:
                self._renderer.move(player, (x, y))
            self._board[x][y] = WHITE
            self._player = BLACK

        self._last_move = action

    def clear(self):
        self._board = [[0 for i in range(self._board_size)] for i in range(self._board_size)]
        self._player = BLACK
        self._winner = 0
        self._round = 0
        self._last_move = None
        if self._display:
            self._renderer.paint_background()
            while not self._renderer.is_initialized():
                time.sleep(.1)

    def read(self, new_board):
        self.clear()
        black_num = 0
        white_num = 0

        for row in range(self._board_size):
            for col in range(self._board_size):
                if new_board[row][col] == BLACK:
                    self.move(1, (row, col))
                    black_num += 1
                elif new_board[row][col] == WHITE:
                    self.move(-1, (row, col))
                    white_num += 1

        self._round = black_num
        if black_num == white_num:
            self._player = BLACK
        elif black_num == white_num + 1:
            self._player = WHITE
        else:
            print("Illegal Position")

    def round(self):
        return self._round

    def current_player(self):
        return self._player

    def last_move(self):
        return self._last_move

    def stone_num(self):
        if self._player == BLACK:
            return 2*self._round
        else:
            return 2*self._round - 1


