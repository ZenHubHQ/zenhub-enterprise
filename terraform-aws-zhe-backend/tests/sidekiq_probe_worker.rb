# frozen_string_literal: true

# Loaded by the Sidekiq 7.3.1 CLI (`sidekiq -r`), the same `sidekiq` command
# the raptor-sidekiq-worker deployment runs. The class exists so a forged
# queue payload can name a job the process will constantize and perform.
require "sidekiq"

class ZheProbeJob
  include Sidekiq::Job

  sidekiq_options retry: false, queue: "default"

  def perform(marker_path, argument)
    File.write(marker_path, argument.to_s)
  end
end
