def _animate(self):
      pid = PID(1, 0.1, 0.05, setpoint=self._speed, sample_time=self._speed)
      pidOff = False
      correction = 0
      loopTime = self._speed

      renderTimer = time.time()
      renderCounter = 0

      while self._running:
          renderCounter += 1
          if renderTimer + 5 < time.time():
              self._fps = renderCounter/5
              if self._print:
                  print(f"Rendering at {self._fps:2.2f}.  Queue length is {self._queue.qsize()}.")
              renderCounter = 0
              renderTimer = time.time()

          # Disable pid while waiting to be activated
          pid.set_auto_mode(False)
          self._activeEvent.wait()

          # Activated!  Re-enable PID, begin processing
          pid.set_auto_mode(True, last_output=correction)
          correction = pid(loopTime)
          startLoop = time.time()
          if self._speed + correction > 0:
              time.sleep(self._speed + correction)

          # Render new image
          img, updated = self._render(self._Force)

          # Disable PID while trying to place new render in queue
          pid.set_auto_mode(False)
          putStart = time.time()
          if self._Force:
              self._Force = False

              self._emptyQueue()

              # Must put value in queue before clearing the forceRender Event
              # so that the forced render receives the newly computed value
              self._queue.put( (img, updated) )
              self._forceRender.set()
          else:
              self._queue.put( (img, updated) )

          # Correct the loop timer if queue was blocked and restart the PID
          startLoop = startLoop + (time.time()-putStart)
          pid.set_auto_mode(True, last_output=correction)

          loopTime = time.time() - startLoop
