class Bouncing:
    """After `schedule_bounce` is called widget will move according to its `vel` attribute, bouncing off its parent's boundaries.
    """

    vel = 1 + 1j
    pos = 0j
    delay = .3

    def schedule_bounce(self):
        from ... import ScreenManager
        self.bounce = ScreenManager().schedule(self._bounce, delay=self.delay)

    def _bounce(self):
        self.pos += self.vel

        offset = int(bool(getattr(self.parent, "has_border", None)))

        if not offset <= self.pos.real <= self.parent.height - offset - self.height:
            self.vel = -self.vel.conjugate()
            self.pos += 2 * self.vel.real

        if not offset <= self.pos.imag <= self.parent.width - offset - self.width:
            self.vel = self.vel.conjugate()
            self.pos += 2j * self.vel.imag

        self.top = round(self.pos.real)
        self.left = round(self.pos.imag)
