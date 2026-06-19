# Advanced Search Disaster recovery

In case of a disaster that resulted in lost updates, you can use this code snippet to reindex affected projects. Please
update the `TIMESTAMP` before running this snippet. Running this will increase the number of documents in the
[initial indexing queue](https://dashboards.gitlab.net/d/sidekiq-main/sidekiq-overview?from=now-12h&orgId=1&to=now&viewPanel=315),
which could potentially cause alerts. You might want to silence those.

```ruby
TIMESTAMP = 1.week.ago
BATCH_SIZE = 1000

begin
  # Load all active record models that support Advanced Search
  classes = ActiveRecord::Base.descendants.select { |klass| klass.include?(Elastic::ApplicationVersionedSearch) && !klass.include?(Elastic::SnippetsSearch) }

  project_ids = Set.new

  puts "> Collecting lost non-code updates"
  classes.each do |klass|
    puts "-> #{klass.name}"
    klass.where('updated_at > ?', TIMESTAMP).in_batches(of: BATCH_SIZE) do |relation|
      if klass == Project
        project_ids.merge(relation.pluck(:id))
      else
        project_ids.merge(relation.uniq.pluck(:project_id))
      end
    end
  end

  puts "> Loading lost code updates"
  ProjectStatistics.where('updated_at > ?', TIMESTAMP).in_batches(of: BATCH_SIZE) do |relation|
    project_ids.merge(relation.uniq.pluck(:project_id))
  end

  puts "> Queueing updates"
  number_of_batches = (project_ids.size.to_f / BATCH_SIZE).ceil
  project_ids.to_a.each_slice(BATCH_SIZE).each_with_index do |ids, index|
    puts "Batch #{index + 1}/#{number_of_batches} (#{(((index + 1) / number_of_batches.to_f) * 100).round(2)}%)"

    Project.where(id: ids).each do |project|
      next unless project.use_elasticsearch?

      ::Elastic::ProcessInitialBookkeepingService.backfill_projects!(project)
    end
  end
  puts "> DONE"
end
```
