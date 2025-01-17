"""Enemy missiles."""

from random import Random

import cv2
import numpy as np

from gym_missile_command.configuration import CONFIG
from gym_missile_command.utils import get_cv2_xy


class EnemyMissiles:
    """Enemy missiles class.

    Enemy missiles are created by the environment.

    Attributes:
        enemy_missiles (numpy array): of size (N, 8)  with N the number of
            enemy missiles present in the environment. The features are: (0)
            initial x position, (1) initial y position, (2) current x position,
            (3) current y position, (4) final x position, (5) final y position,
            (6) horizontal speed vx and (7) vertical speed vy.
        nb_missiles_launched (int): the number of enemy missiles launched in
            the environment.
    """

    def __init__(self):
        """Initialize missiles."""
        self.start_pos_range_cur = CONFIG.ENEMY_MISSILES.START_POS_RANGE_CUR \
            if CONFIG.ENEMY_MISSILES.START_POS_RANGE_CUR is not None else [(-0.5, 0.5)]
        self.end_pos_range_cur = CONFIG.ENEMY_MISSILES.END_POS_RANGE_CUR \
            if CONFIG.ENEMY_MISSILES.END_POS_RANGE_CUR is not None else [(-0.5, 0.5)]
        self.start_pos_range = self.start_pos_range_cur.pop(0)
        self.end_pos_range = self.end_pos_range_cur.pop(0)

    def advance_curriculum(self):
        if len(self.start_pos_range_cur) > 0:
            self.start_pos_range = self.start_pos_range_cur.pop(0)
        else:
            self.start_pos_range = (-0.5, 0.5)
        if len(self.end_pos_range_cur) > 0:
            self.end_pos_range = self.end_pos_range_cur.pop(0)
        else:
            self.end_pos_range = (-0.5, 0.5)

    def set_start_pos_range(self, left, right):
        assert -0.5 <= left <= 0.5
        assert -0.5 <= right <= 0.5
        self.start_pos_range = (left, right)

    def set_end_pos_range(self, left, right):
        assert -0.5 <= left <= 0.5
        assert -0.5 <= right <= 0.5
        self.end_pos_range = (left, right)

    def _launch_missile(self):
        """Launch a new missile.

        - 0) Generate initial and final positions.
        - 1) Compute speed vectors.
        - 2) Add the new missile.
        """
        # Generate initial and final positions
        # ------------------------------------------

        # Initial position
        x0 = self._rng_python.uniform(
            self.start_pos_range[0] * CONFIG.EPISODE.WIDTH, self.start_pos_range[1] * CONFIG.EPISODE.WIDTH)
        y0 = CONFIG.EPISODE.HEIGHT

        # Final position
        x1 = self._rng_python.uniform(
            self.end_pos_range[0] * CONFIG.EPISODE.WIDTH, self.end_pos_range[1] * CONFIG.EPISODE.WIDTH)
        y1 = 0.0

        # Compute speed vectors
        # ------------------------------------------

        # Compute norm
        norm = np.sqrt(np.square(x1 - x0) + np.square(y1 - y0))

        # Compute unit vectors
        ux = (x1 - x0) / norm
        uy = (y1 - y0) / norm

        # Compute speed vectors
        vx = CONFIG.ENEMY_MISSILES.SPEED * ux
        vy = CONFIG.ENEMY_MISSILES.SPEED * uy

        # Add the new missile
        # ------------------------------------------

        # Create the missile
        new_missile = np.array(
            [[x0, y0, x0, y0, x1, y1, vx, vy]],
            dtype=np.float32,
        )

        # Add it to the others
        self.enemy_missiles = np.vstack(
            (self.enemy_missiles, new_missile))

        # Increase number of launched missiles
        self.nb_missiles_launched += 1

    def reset(self, seed=None):
        """Reset enemy missiles.

        Warning:
            To fully initialize a EnemyMissiles object, init function and reset
            function must be called.

        Args:
            seed (int): seed for reproducibility.
        """
        self.enemy_missiles = np.zeros((0, 8), dtype=np.float32)
        self.nb_missiles_launched = 0

        # Create random numbers generator
        self._rng_python = Random(seed)

    def step(self, action):
        """Go from current step to next one.

        - 0) Moving missiles.
        - 1) Potentially launch a new missile.
        - 2) Remove missiles that hit the ground.

        Collisions with friendly missiles and / or cities are checked in the
        main environment class.

        Notes:
            From one step to another, a missile could exceed its final
            position, so we need to do some verification. This issue is due to
            the discrete nature of environment, decomposed in time steps.

        Args:
            action (int): (0) do nothing, (1) target up, (2) target down, (3)
                target left, (4) target right, (5) fire missile.

        returns:
            observation: None.

            reward: None.

            done (bool): True if the episode is finished, i.d. there are no
                more enemy missiles in the environment and no more enemy
                missiles to be launch. False otherwise.

            info: None.
        """
        # Moving missiles
        # ------------------------------------------

        # Compute horizontal and vertical distances to targets
        dx = np.abs(self.enemy_missiles[:, 4] - self.enemy_missiles[:, 2])
        dy = np.abs(self.enemy_missiles[:, 5] - self.enemy_missiles[:, 3])

        # Take the minimum between the actual speed and the distance to target
        movement_x = np.minimum(np.abs(self.enemy_missiles[:, 6]), dx)
        movement_y = np.minimum(np.abs(self.enemy_missiles[:, 7]), dy)

        # Keep the right sign
        movement_x *= np.sign(self.enemy_missiles[:, 6])
        movement_y *= np.sign(self.enemy_missiles[:, 7])

        # Step t to step t+1
        self.enemy_missiles[:, 2] += movement_x
        self.enemy_missiles[:, 3] += movement_y

        # Potentially launch a new missile
        # ------------------------------------------

        if self.nb_missiles_launched < CONFIG.ENEMY_MISSILES.NUMBER:
            if self._rng_python.random() <= CONFIG.ENEMY_MISSILES.PROBA_IN:
                self._launch_missile()

        # Remove missiles that hit the ground
        # ------------------------------------------

        missiles_out_indices = np.squeeze(np.argwhere(
            (self.enemy_missiles[:, 2] == self.enemy_missiles[:, 4]) &
            (self.enemy_missiles[:, 3] == self.enemy_missiles[:, 5])
        ))

        self.enemy_missiles = np.delete(
            self.enemy_missiles, missiles_out_indices, axis=0)

        done = self.enemy_missiles.shape[0] == 0 and \
            self.nb_missiles_launched == CONFIG.ENEMY_MISSILES.NUMBER
        return None, None, done, None

    def render(self, observation):
        """Render enemy missiles.

        For each enemy missiles, draw a line of its trajectory and the actual
        missile.

        Args:
            observation (numpy.array): the current environment observation
                representing the pixels. See the object description in the main
                environment class for information.
        """
        for x0, y0, x, y in zip(self.enemy_missiles[:, 0],
                                self.enemy_missiles[:, 1],
                                self.enemy_missiles[:, 2],
                                self.enemy_missiles[:, 3]):
            cv2.line(
                img=observation,
                pt1=(get_cv2_xy(CONFIG.EPISODE.HEIGHT,
                                CONFIG.EPISODE.WIDTH,
                                x0,
                                y0)),
                pt2=(get_cv2_xy(CONFIG.EPISODE.HEIGHT,
                                CONFIG.EPISODE.WIDTH,
                                x,
                                y)),
                color=CONFIG.COLORS.ENEMY_MISSILE,
                thickness=1,
            )

            cv2.circle(
                img=observation,
                center=(get_cv2_xy(CONFIG.EPISODE.HEIGHT,
                                   CONFIG.EPISODE.WIDTH,
                                   x,
                                   y)),
                radius=int(CONFIG.ENEMY_MISSILES.RADIUS),
                color=CONFIG.COLORS.ENEMY_MISSILE,
                thickness=-1,
            )
