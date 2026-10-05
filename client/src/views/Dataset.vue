<template>
  <div @mousemove="mouseMove">
    <div style="padding-top: 55px" />
    
    <div
      class="bg-light"
      :style="{ 'margin-left': sidebar.width + 'px' }"
    >
      <nav class="nav border-bottom shadow-sm" style="background-color: #4b5162">
        <a class="btn tab" @click="tab = 'images'" :style="{'color': tab == 'images' ? 'white' : 'darkgray'}">
          <i class="fa fa-picture-o" aria-hidden="true"></i> {{ $t('dataset.images') }}
        </a>
        <a class="btn tab" @click="tab = 'exports'" :style="{'color': tab == 'exports' ? 'white' : 'darkgray'}">
          <i class="fa fa-share" aria-hidden="true"></i> {{ $t('dataset.exports') }}
        </a>
        <a class="btn tab" @click="tab = 'members'" :style="{'color': tab == 'members' ? 'white' : 'darkgray'}">
          <i class="fa fa-users" aria-hidden="true"></i> {{ $t('dataset.members') }}
        </a>
        <a class="btn tab" @click="tab = 'statistics'" :style="{'color': tab == 'statistics' ? 'white' : 'darkgray'}">
          <i class="fa fa-bar-chart" aria-hidden="true"></i> {{ $t('dataset.statistics') }}
        </a>
        <a class="btn tab" @click="tab = 'settings'" :style="{'color': tab == 'settings' ? 'white' : 'darkgray'}">
          <i class="fa fa-cog" aria-hidden="true"></i> {{ $t('dataset.settings') }}
        </a>
      </nav>
    
      <div class="bg-light text-start" style="overflow: auto; height: calc(100vh - 100px); margin: 10px">
        <div class="container" v-show="tab == 'images'">
          
          <ol class="breadcrumb">
            <li class="breadcrumb-item"></li>
            <li class="breadcrumb-item active">
              <button class="btn btn-sm btn-link" @click="folders = []">
                {{ dataset.name }}
              </button>
            </li>
            <li
              v-for="(folder, folderId) in folders"
              :key="folderId"
              class="breadcrumb-item"
            >
              <button
                class="btn btn-sm btn-link"
                :disabled="folders[folders.length - 1] === folder"
                @click="removeFolder(folder)"
              >
                {{ folder }}
              </button>
            </li>
          </ol>

          <p class="text-center" v-if="images.length < 1">
            {{ $t('dataset.noImagesFoundInDirectory') }}
          </p>
          <div v-else>
            <Pagination :pages="pages" @pagechange="updatePage" />
            <div class="row">
              <ImageCard v-for="image in images" :key="image.id" :image="image" />
            </div>
            <Pagination :pages="pages" @pagechange="updatePage" />
          </div>

        </div>
        <div class="container-fluid exports-tab" v-show="tab == 'exports'">
          <div class="card my-3 p-3 shadow-sm">
            <div class="d-flex align-items-center border-bottom border-gray pb-2">
              <h6 class="mb-0 me-auto"><b>{{ $t('dataset.exports') }}</b></h6>
              <button type="button" class="btn btn-sm btn-outline-secondary" @click="getExports">
                <i class="fa fa-refresh" /> {{ $t('exportList.refresh') }}
              </button>
            </div>

            <div v-if="!datasetExports.length" class="text-muted small pt-3">
              {{ $t('exportList.empty') }}
            </div>
            <div v-else class="table-responsive">
              <table class="table table-sm table-hover align-middle mb-0 export-table">
                <thead>
                  <tr>
                    <th class="text-nowrap text-center">{{ $t('exportList.id') }}</th>
                    <th class="text-nowrap text-center">{{ $t('exportList.format') }}</th>
                    <th class="text-center">{{ $t('exportList.categories') }}</th>
                    <th class="text-nowrap text-center">{{ $t('exportList.time') }}</th>
                    <th class="text-nowrap text-center">{{ $t('exportList.download') }}</th>
                    <th class="text-nowrap text-center">{{ $t('exportList.delete') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="exp in datasetExports" :key="exp.id">
                    <td class="text-nowrap fw-semibold text-center">#{{ exp.id }}</td>
                    <td class="text-nowrap text-center">
                      <span class="badge" :class="exp.format === 'YOLO' ? 'text-bg-primary' : 'text-bg-dark'">
                        {{ exp.format }}
                      </span>
                      <div v-if="exp.yolo_task" class="small text-muted">{{ $t('yolo.' + exp.yolo_task) }}</div>
                      <div v-if="exp.folder" class="small text-muted">
                        <i class="fa fa-folder-o" /> {{ exp.folder }}/
                      </div>
                      <div
                        v-for="part in splitParts(exp)"
                        :key="part"
                        class="small text-muted lh-sm"
                        :title="$t('exportList.seed', { seed: exp.seed })"
                      >{{ part }}</div>
                    </td>
                    <td class="text-center">
                      <span
                        v-for="name in shownCategories(exp)"
                        :key="name"
                        class="badge text-bg-light border me-1"
                      >{{ name }}</span>
                      <a
                        v-if="(exp.categories || []).length > EXPORT_TAGS_SHOWN"
                        href="#"
                        class="small"
                        @click.prevent="toggleExportTags(exp.id)"
                      >{{ expandedExports.includes(exp.id)
                        ? $t('exportList.less')
                        : $t('exportList.more', { n: exp.categories.length - EXPORT_TAGS_SHOWN }) }}</a>
                    </td>
                    <td class="text-nowrap text-center">
                      {{ exportTime(exp) }}
                      <div class="small text-muted">{{ $t('dataset.exportedAgo', { time: $ago(exp.ago) }) }}</div>
                    </td>
                    <td class="text-center text-nowrap">
                      <button
                        class="btn btn-sm btn-success"
                        :disabled="exp.exists === false || downloadingExport === exp.id"
                        :title="exp.exists === false ? $t('exportList.missing') : ''"
                        @click="downloadExport(exp)"
                      >
                        <i class="fa" :class="downloadingExport === exp.id ? 'fa-spinner fa-spin' : 'fa-download'" />
                        {{ $t('exportList.download') }}
                      </button>
                      <div class="small text-muted">
                        {{ exp.exists === false ? $t('exportList.missing') : fileSize(exp.size) }}
                      </div>
                    </td>
                    <td class="text-center">
                      <button
                        class="btn btn-sm btn-outline-danger"
                        :title="$t('exportList.delete')"
                        @click="deleteExport(exp)"
                      >
                        <i class="fa fa-trash" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="container" v-show="tab == 'members'">

          <div class="card my-3 p-3 shadow-sm me-2">
            <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.inviteMembers') }}</b></h6>
            
          </div>
          
          <div class="card my-3 p-3 shadow-sm me-2">
            <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.existingMembers') }}</b></h6>
            
            <div class="d-flex align-items-start text-muted pt-3" v-for="user in users" :key="user.username">
              <img :src="userAvatar" class="me-2 rounded" style="width: 32px; height: 32px;">
              <div class="flex-grow-1 pb-3 mb-0 small lh-125 border-bottom border-gray">
                <div class="d-flex justify-content-between align-items-center w-100">
                  <div class="text-gray-dark">
                    <strong>{{ user.name }}</strong> @{{user.username}}
                  </div>
                  <a href="#">{{ user.group }}</a>
                </div>
                <span class="d-block">{{ lastSeen(user) }}</span>
              </div>
            </div>
          </div>

        </div>
        <div class="container" v-show="tab == 'statistics'">
          <div v-if="stats == null">
            {{ $t('dataset.crunchingNumbers') }}
          </div>

          <div v-else>
            <div class="row">
              
              <div v-if="stats.total" class="card my-3 p-3 shadow-sm col-3 me-2">
                <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.total') }}</b></h6>
                <div class="row" v-for="stat in Object.keys(stats.total)" :key="stat">
                  <strong class="col-8">{{ $tr('stat', stat) }}:</strong>
                  <span class="col-4">{{stats.total[stat].toFixed(0)}}</span>
                </div>
              </div>

              <div v-if="stats.average" class="card my-3 p-3 shadow-sm col-4 me-2">
                <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.average') }}</b></h6>
                <div class="row" v-for="stat in Object.keys(stats.average)" :key="stat">
                  <strong class="col-8">{{ $tr('stat', stat) }}:</strong>
                  <span class="col-4">{{stats.average[stat].toFixed(0)}}</span>
                </div>
              </div>

              <div v-if="stats.categories" class="card my-3 p-3 shadow-sm col-4 me-2">
                <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.annotationsPerCategory') }}</b></h6>
                <div class="row" v-for="stat in Object.keys(stats.categories)" :key="stat">
                  <strong class="col-8">{{stat}}:</strong>
                  <span class="col-4">{{stats.categories[stat].toFixed(0)}}</span>
                </div>
              </div>

              <div v-if="stats.images_per_category" class="card my-3 p-3 shadow-sm col-4 me-2">
                <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.annotatedImagesPerCategory') }}</b></h6>
                <div class="row" v-for="stat in Object.keys(stats.images_per_category)" :key="stat">
                  <strong class="col-8">{{stat}}:</strong>
                  <span class="col-4">{{stats.images_per_category[stat].toFixed(0)}}</span>
                </div>
              </div>

              <div v-if="stats.users" class="card my-3 p-3 shadow-sm col-6 me-2">
                <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.annotationsPerUser') }}</b></h6>
                <h6 class="row border-bottom border-gray pb-2">
                    <span class="col-4">{{ $t('dataset.username') }}</span>
                    <span class="col-4">{{ $t('dataset.annotations') }}</span>
                    <span class="col-4">{{ $t('dataset.images') }}</span>
                </h6>
                <div class="row" v-for="stat in Object.keys(stats.users)" :key="stat">
                  <strong class="col-4">{{stat}}:</strong>
                  <span class="col-4">{{stats.users[stat]["annotations"].toFixed(0)}}</span>
                  <span class="col-4">{{stats.users[stat]["images"].toFixed(0)}}</span>
                </div>
              </div>

            </div>
            
          </div>
        </div>
        <div class="container" v-show="tab == 'settings'">
          <div class="card my-3 p-3 shadow-sm me-2">
            <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.metadata') }}</b></h6>
            
            <button 
              class="btn btn-sm w-100 btn-danger"
              @click="resetMetadata"
            >
              {{ $t('dataset.restAllMetadata') }}
            </button>
          </div>
        </div>

      </div>
    </div>

    <div
      id="filter"
      ref="sidebar"
      class="sidebar"
      :style="{ width: sidebar.width + 'px' }"
    >
      <div style="padding-top: 10px" />
      <h3>{{ dataset.name }}</h3>
      <p class="text-center" style="color: lightgray">
        <i18n-t keypath="dataset.totalImages" tag="span">
          <template #images><strong style="color: white">{{ imageCount }}</strong></template>
          <template #pages><strong style="color: white">{{ pages }}</strong></template>
        </i18n-t>
      </p>
      <div class="row justify-content-md-center sidebar-section-buttons">
        <button
          type="button"
          class="btn btn-secondary w-100"
          @click="createScanTask"
        >
          <div v-if="scan.id != null" class="progress">
            <div
              class="progress-bar bg-secondary"
              :style="{ 'width': `${scan.progress}%` }"
            >
              {{ $t('dataset.scanning') }}
            </div>
          </div>
          <div v-else>{{ $t('dataset.scan') }}</div>
        </button>

        <button
          type="button"
          class="btn btn-primary w-100"
          @click="importModal"
        >
          <div v-if="importing.id != null" class="progress">
            <div
              class="progress-bar bg-primary"
              :style="{ 'width': `${importing.progress}%` }"
            >
              {{ $t('dataset.importing') }}
            </div>
          </div>
          <div v-else>{{ $t('dataset.importCoco') }}</div>
        </button>

        <button
          type="button"
          class="btn btn-dark w-100"
          @click="exportModal"
        >
          <div v-if="exporting.id != null" class="progress">
            <div
              class="progress-bar bg-dark"
              :style="{ 'width': `${exporting.progress}%` }"
            >
              {{ $t('dataset.exporting') }}
            </div>
          </div>
          <div v-else>{{ $t('dataset.exportCoco') }}</div>
        </button>

        <button
          type="button"
          class="btn btn-info w-100"
          @click="modelModal"
        >
          <div v-if="preannotating.id != null" class="progress">
            <div
              class="progress-bar bg-info"
              :style="{ 'width': `${preannotating.progress}%` }"
            >
              {{ $t('modelRun.running') }}
            </div>
          </div>
          <div v-else><i class="fa fa-rocket" /> {{ $t('modelRun.datasetButton') }}</div>
        </button>
      </div>
      <hr>
      <h6 class="sidebar-title text-center">{{ $t('dataset.subdirectories') }}</h6>
      <div class="sidebar-section" style="max-height: 30%; color: lightgray">
        <div v-if="subdirectories.length > 0">
          <button
            v-for="(subdirectory, subId) in subdirectories"
            :key="subId"
            class="btn badge rounded-pill text-bg-primary category-badge"
            style="margin: 2px"
            @click="folders.push(subdirectory)"
          >
            {{ subdirectory }}
          </button>
        </div>
        <p v-else style="margin: 0; font-size: 13px; color: gray">
          {{ $t('dataset.noSubdirectoryFound') }}
        </p>
      </div>
      <hr>
      <h6 class="sidebar-title text-center">{{ $t('dataset.filteringOptions') }}</h6>
      <div
        class="sidebar-section"
        style="max-height: 30%; color: lightgray"
      >
        <PanelString :name="$t('dataset.contains')" v-model:value="query.file_name__icontains" @submit="updatePage" />
        <PanelToggle :name="$t('dataset.showAnnotated')" v-model:value="panel.showAnnotated" />
        <PanelToggle :name="$t('dataset.showNotAnnotated')" v-model:value="panel.showNotAnnotated" />
        <PanelDropdown :name="$t('dataset.order')" v-model:value="order" :values="orderTypes" />
      </div>
        <div
          class="sidebar-section"
          style="max-height: 30%; color: lightgray"
        >
          <div class="mb-3">
            <label>{{ $t('dataset.showAnnotatedCategories') }} </label>
            <TagsInput
              v-model:value="selected.categories"
              element-id="selectedCategories"
              :title="$t('dataset.onlyShowsImagesAnnotatedWith')"
              :existing-tags="categoryTags"
              :typeahead="true"
              :typeahead-activation-threshold="0"
            ></TagsInput>
          </div>
      </div>
    </div>


    <div class="modal fade" tabindex="-1" role="dialog" id="cocoUpload">
      <div class="modal-dialog" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('dataset.uploadCocoAnnotaitons') }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            <form>
              <div class="mb-3">
                <label for="coco" class="form-label">{{ $t('dataset.cocoAnnotationFileJson') }}</label>
                <input
                  type="file"
                  class="form-control"
                  id="coco"
                  accept=".json,application/json,.zip,application/zip"
                  @change="importFile = $event.target.files[0] || null"
                />
                <div class="form-text">{{ importIsYolo ? $t('yolo.importHint') : $t('dataset.importHint') }}</div>
              </div>
              <div v-if="importIsYolo" class="mb-3">
                <label for="importYoloTask" class="form-label">{{ $t('yolo.task') }}</label>
                <select id="importYoloTask" v-model="importYoloTask" class="form-select">
                  <option value="auto">{{ $t('yolo.auto') }}</option>
                  <option v-for="t in yoloTasks" :key="t" :value="t">{{ $t('yolo.' + t) }}</option>
                </select>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-primary"
              @click="importCOCO"
              :disabled="!importFile"
              data-bs-dismiss="modal"
            >
              {{ $t('dataset.upload') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {{ $t('dataset.close') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" tabindex="-1" role="dialog" id="exportDataset">
      <div class="modal-dialog" role="document">
        <div class="modal-content text-start">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('dataset.exportTitle', { name: dataset.name }) }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body pt-2">
            <!-- step indicator -->
            <ol class="export-steps">
              <li
                v-for="(name, i) in exportStepNames"
                :key="name"
                :class="{
                  active: exporting.step === i + 1,
                  done: exporting.step > i + 1 && !stepSkipped(i + 1),
                  skipped: stepSkipped(i + 1),
                  disabled: !canGoToStep(i + 1)
                }"
                @click="goToStep(i + 1)"
              >
                <span class="step-dot">
                  <i v-if="stepSkipped(i + 1)" class="fa fa-minus" />
                  <i v-else-if="exporting.step > i + 1" class="fa fa-check" />
                  <template v-else>{{ i + 1 }}</template>
                </span>
                <span class="step-name">{{ $t('exportSteps.' + name) }}</span>
              </li>
            </ol>

            <form @submit.prevent>
              <!-- step 1: format -->
              <div v-show="exporting.step === 1">
                <div class="form-label fw-semibold">{{ $t('yolo.format') }}</div>
                <div class="row g-2 mb-3">
                  <div v-for="f in ['coco', 'yolo']" :key="f" class="col-6">
                    <label class="choice-card" :class="{ selected: exporting.format === f }">
                      <input v-model="exporting.format" type="radio" name="exportFormat" :value="f" class="d-none" />
                      <span class="fw-semibold">{{ f.toUpperCase() }}</span>
                      <span class="small text-muted">{{ $t('exportSteps.formatHint.' + f) }}</span>
                    </label>
                  </div>
                </div>

                <template v-if="exporting.format === 'yolo'">
                  <div class="form-label fw-semibold">{{ $t('yolo.task') }}</div>
                  <div class="row g-2">
                    <div v-for="t in exportYoloTasks" :key="t" class="col-6">
                      <label class="choice-card" :class="{ selected: exporting.yolo_task === t }">
                        <input v-model="exporting.yolo_task" type="radio" name="exportYoloTask" :value="t" class="d-none" />
                        <span class="fw-semibold">{{ $t('yolo.' + t) }}</span>
                        <span class="small text-muted">{{ $t('yolo.exportHint.' + t) }}</span>
                      </label>
                    </div>
                  </div>
                  <div class="form-check d-flex align-items-center gap-2 ps-0 mt-3">
                    <input
                      id="exportWithImages"
                      type="checkbox"
                      class="form-check-input m-0"
                      :checked="exportWithImages"
                      :disabled="exporting.yolo_task === 'classify'"
                      @change="exporting.with_images = $event.target.checked"
                    />
                    <label class="form-check-label mb-0" for="exportWithImages">{{ $t('yolo.withImages') }}</label>
                  </div>
                  <div v-if="exporting.yolo_task === 'classify'" class="form-text mt-0 ms-4">{{ $t('yolo.classifyImages') }}</div>
                  <div class="form-text mt-2">
                    <i class="fa fa-info-circle" />
                    {{ $t('exportSteps.prefixExample', { image: exportExampleName.image, label: exportExampleName.label }) }}
                  </div>

                </template>
              </div>

              <!-- step 2: folder (YOLO) -->
              <div v-show="exporting.step === 2">
                <template v-if="exporting.format === 'yolo'">
                  <label class="form-label fw-semibold mb-1" for="exportFolder">{{ $t('exportSteps.folder') }}</label>
                  <input
                    id="exportFolder"
                    v-model="exporting.folder"
                    class="form-control"
                    :class="{ 'is-invalid': !exportFolderName }"
                    maxlength="100"
                    :placeholder="defaultExportFolder"
                  />
                  <div v-if="!exportFolderName" class="invalid-feedback">{{ $t('exportSteps.folderRequired') }}</div>
                  <div v-else-if="exportFolderName !== exporting.folder.trim()" class="form-text">
                    {{ $t('exportSteps.folderCleaned', { name: exportFolderName }) }}
                  </div>
                  <div class="form-text">{{ $t('exportSteps.folderHint') }}</div>
                  <pre class="zip-tree small mb-0 mt-2">{{ exportTree }}</pre>
                </template>
                <div v-else class="text-muted small">{{ $t('exportSteps.folderCoco') }}</div>
              </div>

              <!-- step 3: categories -->
              <div v-show="exporting.step === 3">
                <ExportCategories
                  v-model:order="exporting.order"
                  v-model:selected="exporting.categories"
                  :categories="categories"
                  :counts="exporting.counts && exporting.counts.categories"
                  :yolo-task="exporting.format === 'yolo' ? exporting.yolo_task : null"
                />
                <div class="form-check d-flex align-items-center gap-2 ps-0 mt-3">
                  <input id="exportWithEmpty" v-model="exporting.with_empty_images" type="checkbox" class="form-check-input m-0" />
                  <label class="form-check-label mb-0" for="exportWithEmpty">{{ $t('dataset.exportWithNotAnnotatedImages') }}</label>
                </div>
              </div>

              <!-- step 4: split -->
              <div v-show="exporting.step === 4">
                <ExportSplit
                  v-model:enabled="exporting.split_on"
                  v-model:ratios="exporting.split"
                  v-model:seed="exporting.seed"
                  :image-count="exportImageCount"
                  :yolo="exporting.format === 'yolo'"
                />
              </div>

              <!-- step 5: review -->
              <div v-show="exporting.step === 5">
                <div class="export-summary">
                  <dl class="row small mb-0">
                    <dt class="col-4">{{ $t('yolo.format') }}</dt>
                    <dd class="col-8">
                      {{ exporting.format.toUpperCase() }}
                      <template v-if="exporting.format === 'yolo'">
                        · {{ $t('yolo.' + exporting.yolo_task) }}
                        <template v-if="exporting.with_images"> · {{ $t('exportSteps.withImages') }}</template>
                        <div class="text-muted">
                          {{ $t('exportSteps.prefixSummary', { image: exportExampleName.image }) }}
                        </div>
                      </template>
                      <a href="#" class="ms-1 small" @click.prevent="goToStep(1)">{{ $t('exportSteps.edit') }}</a>
                    </dd>
                    <template v-if="exporting.format === 'yolo'">
                      <dt class="col-4">{{ $t('exportSteps.folder') }}</dt>
                      <dd class="col-8">
                        {{ exportFolderName }}/
                        <a href="#" class="ms-1 small" @click.prevent="goToStep(2)">{{ $t('exportSteps.edit') }}</a>
                      </dd>
                    </template>
                    <dt class="col-4">{{ $t('exportSteps.categories') }}</dt>
                    <dd class="col-8">
                      {{ $t('exportSteps.categoryCount', { n: exportSelectedNames.length, names: exportSelectedNames.join($t('exportSteps.separator')) }) }}
                      <a href="#" class="ms-1 small" @click.prevent="goToStep(3)">{{ $t('exportSteps.edit') }}</a>
                      <div v-if="exporting.with_empty_images" class="text-muted">{{ $t('dataset.exportWithNotAnnotatedImages') }}</div>
                    </dd>
                    <dt class="col-4">{{ $t('exportSteps.contents') }}</dt>
                    <dd class="col-8">
                      <template v-if="exportImageCount == null"><i class="fa fa-spinner fa-spin" /></template>
                      <template v-else>
                        <template v-if="exporting.format === 'yolo' && exporting.yolo_task === 'classify'">
                          {{ $t('exportSteps.classifyCount', { images: exportImageCount }) }}
                        </template>
                        <template v-else>
                          {{ $t('exportSteps.contentCount', { images: exportImageCount, annotations: exportAnnotationCount }) }}
                        </template>
                      </template>
                    </dd>
                    <dt class="col-4">{{ $t('exportSteps.split') }}</dt>
                    <dd class="col-8 mb-0">
                      <template v-if="exporting.split_on">
                        <span v-for="k in ['train', 'val', 'test']" :key="k" class="me-2">
                          {{ $t('exportSplit.' + k) }} {{ exporting.split[k] }}%
                          <span class="text-muted">({{ exportSplitSizes[k] }})</span>
                        </span>
                        <div class="text-muted">{{ $t('exportSplit.seed') }} {{ exporting.seed }}</div>
                      </template>
                      <template v-else>{{ $t('exportSteps.noSplit') }}</template>
                      <a href="#" class="ms-1 small" @click.prevent="goToStep(4)">{{ $t('exportSteps.edit') }}</a>
                    </dd>
                  </dl>
                </div>
                <template v-if="exporting.format === 'yolo'">
                  <div class="fw-semibold small mt-3 mb-1">{{ $t('exportSteps.zipContents') }}</div>
                  <pre class="zip-tree small mb-0">{{ exportTree }}</pre>
                  <div class="form-text">
                    {{ $t('exportSteps.trainWith') }}
                    <code>{{ exportTrainCommand }}</code>
                  </div>
                </template>
                <div v-if="!exportReady" class="small text-danger mt-2">{{ $t('exportSteps.notReady') }}</div>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button
              v-if="exporting.step > 1"
              type="button"
              class="btn btn-outline-secondary me-auto"
              @click="stepBy(-1)"
            >
              <i class="fa fa-chevron-left" /> {{ $t('exportSteps.back') }}
            </button>
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('dataset.close') }}
            </button>
            <button
              v-if="exporting.step < exportStepNames.length"
              type="button"
              class="btn btn-primary"
              :disabled="!canGoToStep(nextStep(1))"
              @click="stepBy(1)"
            >
              {{ $t('exportSteps.next') }} <i class="fa fa-chevron-right" />
            </button>
            <button
              v-else
              type="button"
              class="btn btn-primary"
              :disabled="!exportReady"
              @click="exportCOCO"
            >
              <i class="fa fa-download" /> {{ $t('dataset.export') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <ModelRunModal
      ref="modelRun"
      modal-id="modelRunDataset"
      :dataset="true"
      :dataset-name="dataset.name"
      :category-names="datasetCategoryNames"
      @run="runModel"
    />
  </div>
</template>

<script>
import userAvatar from "@/assets/user.png";
import { hideModal, showModal } from "@/libs/modal";
import toastrs from "@/mixins/toastrs";
import Dataset, { isYoloFile } from "@/models/datasets";
import Export from "@/models/exports";
import ImageCard from "@/components/cards/ImageCard.vue";
import Pagination from "@/components/Pagination.vue";
import PanelString from "@/components/PanelInputString.vue";
import PanelToggle from "@/components/PanelToggle.vue";
import PanelDropdown from "@/components/PanelInputDropdown.vue"
import TagsInput from "@/components/TagsInput.vue";
import ModelRunModal from "@/components/ModelRunModal.vue";
import ExportCategories from "@/components/ExportCategories.vue";
import ExportSplit, { splitSizes, splitValid } from "@/components/ExportSplit.vue";
import axios from "axios";

import { mapMutations } from "vuex";


export default {
  name: "Dataset",
  components: {
    ImageCard,
    ExportCategories,
    ExportSplit,
    Pagination,
    PanelString,
    PanelToggle,
    PanelDropdown,
    TagsInput,
    ModelRunModal
  },
  mixins: [toastrs],
  props: {
    identifier: {
      type: [Number, String],
      required: true
    }
  },
  data() {
    return {
      userAvatar,
      pages: 1,
      limit: 52,
      imageCount: 0,
      categories: [],
      images: [],
      folders: [],
      dataset: {
        id: 0
      },
      users: [],
      subdirectories: [],
      status: {
        data: { state: true, message: "Loading data" }
      },
      mouseDown: false,
      sidebar: {
        drag: false,
        width: window.innerWidth * 0.2,
        canResize: false
      },
      scan: {
        progress: 0,
        id: null
      },
      importing: {
        progress: 0,
        warnings: 0,
        errors: 0,
        id: null
      },
      importPoll: null,
      preannotating: {
        progress: 0,
        id: null
      },
      exporting: {
        categories: [],
        progress: 0,
        with_empty_images: false,
        order: [],
        counts: null,
        step: 1,
        folder: "",
        split_on: false,
        split: { train: 80, val: 20, test: 0 },
        seed: 42,
        format: "coco",
        yolo_task: "detect",
        with_images: false,
        id: null
      },
      yoloTasks: ["detect", "segment", "obb", "pose"],
      exportYoloTasks: ["detect", "segment", "obb", "pose", "classify", "semantic"],
      exportStepNames: ["format", "folder", "categories", "split", "review"],
      importFile: null,
      importYoloTask: "auto",
      selected: {
        categories: []
      },
      datasetExports: [],
      expandedExports: [],
      downloadingExport: null,
      EXPORT_TAGS_SHOWN: 6,
      tab: "images",
      order: "file_name",
      orderTypes: {
        file_name: "File Name",
        id: "Id",
        path: "File Path"
      },
      query: {
        file_name__icontains: "",
        // query string filters (but not the import task id, see created)
        ...Object.fromEntries(Object.entries(this.$route.query).filter(([k]) => k !== "importTask"))
      },
      panel: {
        showAnnotated: true,
        showNotAnnotated: true
      },
      stats: null
    };
  },
  methods: {
    ...mapMutations(["addProcess", "removeProcess"]),
    updatePage(page) {
      let process = "Loading images from dataset";
      this.addProcess(process);

      Dataset.getData(this.dataset.id, {
        page: page,
        limit: this.limit,
        folder: this.folders.join("/"),
        ...this.query,
        annotated: this.queryAnnotated,
        category_ids__in: encodeURI(this.selected.categories),
        order: this.order
      })
        .then(response => {
          let data = response.data;

          this.images = data.images;
          this.dataset = data.dataset;
          this.categories = data.categories;

          this.imageCount = data.total;
          this.pages = data.pages;

          this.subdirectories = data.subdirectories;
          // this.scan.id = data.scanId;
          // this.generate.id = data.generateId;
          // this.importing.id = data.importId;
          // this.exporting.id = data.exportId;
        })
        .catch(error => {
          this.axiosReqestError("Loading Dataset", error.response.data.message);
        })
        .finally(() => this.removeProcess(process));
    },
    getUsers() {
      Dataset.getUsers(this.dataset.id).then(response => {
        this.users = response.data;
      });
    },
    downloadExport(exp) {
      this.downloadingExport = exp.id;
      Export.download(exp.id, this.dataset.name)
        .catch(error => {
          const data = (error.response && error.response.data) || {};
          this.$toastr.error(data.message || this.$t("exportList.downloadFailed"));
        })
        .finally(() => (this.downloadingExport = null));
    },
    deleteExport(exp) {
      if (!confirm(this.$t("exportList.confirmDelete", { id: exp.id }))) return;
      axios
        .delete(`/api/export/${exp.id}`)
        .then(() => {
          this.datasetExports = this.datasetExports.filter(e => e.id !== exp.id);
          this.$toastr.success(this.$t("exportList.deleted", { id: exp.id }));
        })
        .catch(error => {
          const data = (error.response && error.response.data) || {};
          this.$toastr.error(data.message || String(error));
        });
    },
    splitParts(exp) {
      if (!exp.split) return [];
      return ["train", "val", "test"].filter(k => exp.split[k] > 0).map(k => {
        const n = exp.split_counts ? exp.split_counts[k] : null;
        return this.$t("exportList.splitPart", { name: this.$t("exportSplit." + k), pct: exp.split[k], n });
      });
    },
    shownCategories(exp) {
      const names = exp.categories || [];
      return this.expandedExports.includes(exp.id) ? names : names.slice(0, this.EXPORT_TAGS_SHOWN);
    },
    toggleExportTags(id) {
      this.expandedExports = this.expandedExports.includes(id)
        ? this.expandedExports.filter(x => x !== id)
        : [...this.expandedExports, id];
    },
    /** Local date and time of an export (stored in UTC) */
    exportTime(exp) {
      const date = exp.created_at ? new Date(exp.created_at) : null;
      if (!date || isNaN(date)) return "";
      const pad = n => String(n).padStart(2, "0");
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
        `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
    },
    fileSize(bytes) {
      if (bytes == null) return "";
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      if (bytes < 1024 ** 3) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
      return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
    },
    getExports() {
      Dataset.getExports(this.dataset.id).then(response => {
        this.datasetExports = response.data;
      });
    },
    resetMetadata() {
      let r = confirm("You can not undo reseting of all metadata in"
        + "this dataset. This includes metadata of images"
        + "and annotations.");
      
      if (r) {
        Dataset.resetMetadata(this.dataset.id);
      }
    },
    getStats() {
      Dataset.getStats(this.dataset.id).then(response => {
        this.stats = response.data;
      });
    },
    createScanTask() {
      if (this.scan.id != null) {
        this.$router.push({ path: "/tasks", query: { id: this.scan.id } });
        return;
      }

      Dataset.scan(this.dataset.id)
        .then(response => {
          let id = response.data.id;
          this.scan.id = id;
        })
        .catch(error => {
          this.axiosReqestError(
            "Scanning Dataset",
            error.response.data.message
          );
        });
    },
    exportModal() {
      if (this.exporting.id != null) {
        this.$router.push({ path: "/tasks", query: { id: this.exporting.id } });
        return;
      }
      this.prepareExportCategories();
      this.exporting.step = 1;
      if (!this.exporting.folder.trim()) this.exporting.folder = this.defaultExportFolder;
      showModal("#exportDataset");
    },
    /** Steps can be visited in any order once the earlier ones are valid */
    /** Same rules as the server (geometry/yolo_format.py safe_folder) */
    cleanFolderName(name) {
      return String(name || "").replace(/[\\/:*?"<>|\s]+/g, "_").replace(/^[_.]+|[_.]+$/g, "").slice(0, 100);
    },
    /** Step 2 (folder) only applies to YOLO */
    stepSkipped(step) {
      return step === 2 && this.exporting.format !== "yolo";
    },
    nextStep(direction) {
      let step = this.exporting.step + direction;
      while (this.stepSkipped(step)) step += direction;
      return Math.min(Math.max(step, 1), this.exportStepNames.length);
    },
    stepBy(direction) {
      this.goToStep(this.nextStep(direction));
    },
    /** A step is open once every step before it is filled in */
    canGoToStep(step) {
      if (this.stepSkipped(step)) return false;
      if (step > 2 && this.exporting.format === "yolo" && !this.exportFolderName) return false;
      if (step > 3 && !this.exporting.categories.length) return false;
      if (step > 4 && this.exporting.split_on && !this.exportSplitValid) return false;
      return true;
    },
    goToStep(step) {
      if (this.canGoToStep(step)) this.exporting.step = step;
    },
    /** Keep the order / ticks from last time; new categories go last, ticked */
    prepareExportCategories() {
      const ids = this.categories.map(c => c.id);
      const known = new Set(this.exporting.order);
      const order = this.exporting.order.filter(id => ids.includes(id));
      const added = ids.filter(id => !known.has(id));
      this.exporting.order = [...order, ...added];
      this.exporting.categories = [
        ...this.exporting.categories.filter(id => ids.includes(id)),
        ...added
      ];
      this.exporting.counts = null;
      axios
        .get(`/api/dataset/${this.dataset.id}/category_counts`)
        .then(r => (this.exporting.counts = r.data))
        .catch(() => (this.exporting.counts = { categories: {}, image_categories: [], total_images: null }));
    },
    exportCOCO() {
      hideModal("#exportDataset");
      const options = { format: this.exporting.format };
      if (this.exporting.format === "yolo") {
        options.yolo_task = this.exporting.yolo_task;
        options.with_images = this.exportWithImages;
        options.folder = this.exportFolderName;
      }
      if (this.exporting.split_on) {
        const r = this.exporting.split;
        options.split = [r.train, r.val, r.test].map(v => Number(v) || 0).join(",");
        options.seed = this.exporting.seed;
      }
      // ticked categories in the chosen order (= YOLO class index)
      const chosen = new Set(this.exporting.categories);
      const categories = this.exporting.order.filter(id => chosen.has(id));
      Dataset.exportingCOCO(this.dataset.id, categories, this.exporting.with_empty_images, options)
        .then(response => {
          let id = response.data.id;
          this.exporting.id = id;
        })
        .catch(error => {
          this.axiosReqestError("Exporting COCO", error.response.data.message);
        });
    },
    modelModal() {
      if (this.preannotating.id != null) {
        this.$router.push({ path: "/tasks", query: { id: this.preannotating.id } });
        return;
      }
      this.$refs.modelRun.open();
    },
    runModel(options) {
      axios
        .post(`/api/model/yolo/dataset/${this.dataset.id}`, options)
        .then(response => {
          hideModal("#modelRunDataset");
          this.preannotating.id = response.data.id;
          this.$toastr.info(this.$t("modelRun.datasetStarted"));
        })
        .catch(error => {
          const data = (error.response && error.response.data) || {};
          this.axiosReqestError(this.$t("modelRun.datasetButton"), data.message);
        });
    },
    removeFolder(folder) {
      let index = this.folders.indexOf(folder);
      this.folders.splice(index + 1, this.folders.length);
    },
    importModal() {
      if (this.importing.id != null) {
        this.$router.push({ path: "/tasks", query: { id: this.importing.id } });
        return;
      }

      this.importFile = null;
      const input = document.getElementById("coco");
      if (input) input.value = "";
      showModal("#cocoUpload");
    },
    /** Fallback for a progress update sent before this page was listening */
    /** "last seen" text; accounts that never logged in have no date */
    lastSeen(user) {
      const raw = user.last_seen && (user.last_seen["$date"] ?? user.last_seen);
      const date = raw != null ? new Date(raw) : null;
      if (!date || isNaN(date)) return this.$t("dataset.neverSeen");
      const pad = n => String(n).padStart(2, "0");
      const time = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
        `${pad(date.getHours())}:${pad(date.getMinutes())}`;
      return this.$t("dataset.lastSeen", { time });
    },
    pollImportTask() {
      clearTimeout(this.importPoll);
      const id = this.importing.id;
      if (id == null || this.importing.progress >= 100) return;
      axios.get("/api/tasks/").then(response => {
        const task = (response.data || []).find(t => t.id === id);
        if (this.importing.id !== id) return;
        if (task && task.completed) {
          this.importing.warnings = task.warnings || 0;
          this.importing.errors = task.errors || 0;
          this.importing.progress = 100;
        } else {
          this.importPoll = setTimeout(this.pollImportTask, 2000);
        }
      });
    },
    importCOCO() {
      if (!this.importFile) return;
      Dataset.uploadAnnotations(this.dataset.id, this.importFile, this.importYoloTask)
        .then(response => {
          if (response.data.stats) this.showYoloStats(response.data);
          this.importing.id = response.data.id;
          this.pollImportTask();
        })
        .catch(error => {
          const data = (error.response && error.response.data) || {};
          this.axiosReqestError(this.$t("dataset.importCoco"), data.message || String(error));
        });
    },
    /** What the server matched in a YOLO zip (the import itself runs as a task) */
    showYoloStats(data) {
      const s = data.stats;
      this.$toastr.info(this.$t("yolo.importStarted", {
        task: this.$t("yolo." + s.task), matched: s.matched, annotations: s.annotations
      }));
      if (s.unmatched) {
        this.$toastr.warning(this.$t("yolo.unmatched", { n: s.unmatched, names: s.unmatched_examples.join(", ") }));
      }
      if (!data.names_found) this.$toastr.warning(this.$t("yolo.noNames"));
    },
    mouseMove(event) {
      let element = this.$refs.sidebar;

      let sidebarWidth = element.offsetWidth;
      let clickWidth = event.x;
      let pixelsFromSide = Math.abs(sidebarWidth - clickWidth);

      this.sidebar.drag = pixelsFromSide < 4;

      if (this.sidebar.canResize) {
        event.preventDefault();
        let max = window.innerWidth * 0.5;
        this.sidebar.width = Math.min(Math.max(event.x, 150), max);
        localStorage.setItem("dataset/sideWidth", this.sidebar.width)
      }
    },
    startDrag() {
      this.mouseDown = true;
      this.sidebar.canResize = this.sidebar.drag;
    },
    stopDrag() {
      this.mouseDown = false;
      this.sidebar.canResize = false;
    }
  },
  computed: {
    exportSplitValid() {
      return splitValid(this.exporting.split);
    },
    defaultExportFolder() {
      return this.cleanFolderName(this.dataset.name) || "dataset";
    },
    /** The folder name as the server will write it */
    exportFolderName() {
      return this.cleanFolderName(this.exporting.folder);
    },
    exportTrainCommand() {
      const task = this.exporting.yolo_task;
      const data = task === "classify" ? this.exportFolderName : "data.yaml";
      const model = { detect: "yolo26n.pt", segment: "yolo26n-seg.pt", obb: "yolo26n-obb.pt", pose: "yolo26n-pose.pt",
        classify: "yolo26n-cls.pt", semantic: "yolo26n-sem.pt" }[task];
      return `yolo ${task} train data=${data} model=${model}`;
    },
    /** classify always ships the images (they are the dataset) */
    exportWithImages() {
      return this.exporting.yolo_task === "classify" || this.exporting.with_images;
    },
    /** What the zip will contain */
    exportTree() {
      const root = this.exportFolderName || "…";
      const task = this.exporting.yolo_task;
      const split = this.exporting.split_on ? this.exporting.split : null;
      const subsets = split ? ["train", "val", "test"].filter(k => Number(split[k]) > 0) : ["train"];
      const { image, label } = this.exportExampleName;
      const mask = label.replace(/\.txt$/, ".png");
      const lines = task === "classify" ? ["classes.txt", `${root}/`] : ["data.yaml", "classes.txt", `${root}/`];
      const classNames = this.exportSelectedNames.slice(0, 2).map(n => this.cleanFolderName(n) || "class");
      if (this.exportSelectedNames.length > 2) classNames.push("…");
      const children = (pipe, inner) => {
        if (task === "classify") {
          classNames.forEach((name, j) => {
            const end = j === classNames.length - 1;
            lines.push(`${pipe}${end ? "└─ " : "├─ "}${name}/${name === "…" ? "" : "   " + image}`);
          });
          return;
        }
        const leaf = task === "semantic" ? ["masks/", mask] : ["labels/", label];
        if (this.exportWithImages) lines.push(`${pipe}├─ images/   ${image}`);
        lines.push(`${pipe}└─ ${leaf[0].padEnd(9)} ${leaf[1]}`);
        return inner;
      };
      if (task === "classify" && !split) {
        children("");  // class folders directly in the folder; Ultralytics splits 80/20
      } else {
        subsets.forEach((name, i) => {
          const last = i === subsets.length - 1;
          lines.push(`${last ? "└─ " : "├─ "}${name}/`);
          children(last ? "   " : "│  ");
        });
      }
      return lines.join("\n");
    },
    /** e.g. ships_IMG_0001.jpg / .txt, as the server names them */
    exportExampleName() {
      const sample = (this.images[0] && this.images[0].file_name) || "IMG_0001.jpg";
      const base = sample.split(/[\\/]/).pop();
      const dot = base.lastIndexOf(".");
      const stem = dot > 0 ? base.slice(0, dot) : base;
      const ext = dot > 0 ? base.slice(dot) : ".jpg";
      const cleaned = String(this.dataset.name || "").replace(/[\\/:*?"<>|\s]+/g, "_").replace(/^[_.]+|[_.]+$/g, "");
      const name = (cleaned ? `${cleaned}_` : "") + stem;
      return { image: name + ext, label: name + ".txt" };
    },
    exportSplitSizes() {
      return splitSizes(this.exportImageCount || 0, this.exporting.split);
    },
    exportReady() {
      if (this.exporting.format === "yolo" && !this.exportFolderName) return false;
      return this.exporting.categories.length > 0 && (!this.exporting.split_on || this.exportSplitValid);
    },
    exportSelectedNames() {
      const byId = new Map(this.categories.map(c => [c.id, c.name]));
      const chosen = new Set(this.exporting.categories);
      return this.exporting.order.filter(id => chosen.has(id) && byId.has(id)).map(id => byId.get(id));
    },
    /** Annotations the export will contain (pose: only those with keypoints) */
    exportAnnotationCount() {
      const counts = (this.exporting.counts && this.exporting.counts.categories) || {};
      const task = this.exporting.format === "yolo" ? this.exporting.yolo_task : null;
      return this.exporting.categories.reduce((n, id) => {
        const c = counts[id];
        if (!c) return n;
        if (task === "pose") return n + c.keypoints;
        if (task === "semantic") return n + (c.boxes || 0) + (c.rotated || 0) + (c.polygons || 0);
        return n + c.annotations;
      }, 0);
    },
    /** Images the export will contain (for the split estimate) */
    exportImageCount() {
      const counts = this.exporting.counts;
      if (!counts || counts.total_images == null) return null;
      const chosen = new Set(this.exporting.categories);
      const images = counts.image_categories || [];
      if (this.exporting.format === "yolo" && this.exporting.yolo_task === "classify") {
        // classify keeps only images whose annotations are all one category
        return images.filter(cats => new Set(cats.filter(id => chosen.has(id))).size === 1).length;
      }
      const matched = images.filter(cats => cats.some(id => chosen.has(id))).length;
      return this.exporting.with_empty_images ? counts.total_images - images.length + matched : matched;
    },
    importIsYolo() {
      return isYoloFile(this.importFile);
    },
    queryAnnotated() {
      let showAnnotated = this.panel.showAnnotated;
      let showNotAnnotated = this.panel.showNotAnnotated;

      if (showAnnotated && showNotAnnotated) return null;
      if (!showAnnotated && !showNotAnnotated) return " ";

      return showAnnotated;
    },
    datasetCategoryNames() {
      return this.categories.map(c => c.name);
    },
    categoryTags() {
      let tags = {};
      this.categories.forEach(c => tags[c.id] = c.name);
      return tags;
    }
  },
  sockets: {
    taskProgress(data) {
      if (data.id === this.scan.id) {
        this.scan.progress = data.progress;
      }

      if (data.id === this.importing.id) {
        // socket updates can arrive after the poll already saw the task finish
        this.importing.progress = Math.max(this.importing.progress, data.progress);
        this.importing.warnings = data.warnings || 0;
        this.importing.errors = data.errors || 0;
      }

      if (data.id === this.exporting.id) {
        this.exporting.progress = data.progress;
      }

      if (data.id === this.preannotating.id) {
        this.preannotating.progress = data.progress;
      }
    },
    annotating(data) {
      let image = this.images.find(i => i.id == data.image_id);
      if (image == null) return;

      if (data.active) {
        let found = image.annotating.indexOf(data.username);
        if (found < 0) {
          image.annotating.push(data.username);
        }
      } else {
        image.annotating.splice(image.annotating.indexOf(data.username), 1);
      }
    }
  },
  watch: {
    tab(tab) {
      localStorage.setItem("dataset/tab", tab);
      if (tab == "members") this.getUsers();
      if (tab == "statistics") this.getStats();
      if (tab == "exports") this.getExports();
    },
    order(order) {
      localStorage.setItem("dataset/order", order);
      this.updatePage();
    },
    queryAnnotated() {
      this.updatePage();
    },
    "selected.categories": {
      deep: true,
      handler(val) {
        this.updatePage();
      }
    },
    folders: {
      deep: true,
      handler() {
        this.updatePage();
      }
    },
    "sidebar.drag"(canDrag) {
      let el = this.$refs.sidebar;
      if (canDrag) {
        this.$el.style.cursor = "ew-resize";
        el.style.borderRight = "4px solid #383c4a";
      } else {
        this.$el.style.cursor = "default";
        el.style.borderRight = "";
      }
    },
    "scan.progress"(progress) {
      if (progress >= 100) {
        setTimeout(() => {
          this.scan.progress = 0;
          this.scan.id = null;
        }, 1000);
      }
    },
    "importing.progress"(progress, previous) {
      // progress can step from e.g. 100.0000001 to 100: report once
      if (progress >= 100 && !(previous >= 100)) {
        const problems = (this.importing.warnings || 0) + (this.importing.errors || 0);
        if (problems) {
          this.$toastr.warning(this.$t("dataset.importDoneWithProblems", { n: problems }));
        } else {
          this.$toastr.success(this.$t("dataset.importDone"));
        }
        this.updatePage();
        setTimeout(() => {
          this.importing.progress = 0;
          this.importing.id = null;
        }, 1000);
      }
    },
    "preannotating.progress"(progress) {
      if (progress >= 100) {
        setTimeout(() => {
          this.preannotating.progress = 0;
          this.preannotating.id = null;
          this.updatePage();
        }, 1000);
      }
    },
    "exporting.progress"(progress) {
      if (progress >= 100) {
        setTimeout(() => {
          this.exporting.progress = 0;
          this.exporting.id = null;

          this.getExports();
        }, 1000);
      }
    }
  },
  beforeRouteUpdate() {
    this.dataset.id = parseInt(this.identifier);
    this.updatePage();
  },
  created() {
    let tab = localStorage.getItem("dataset/tab");
    let order = localStorage.getItem("dataset/order");
    let sideWidth = localStorage.getItem("dataset/sideWidth");
    
    if (sideWidth !== null) this.sidebar.width = parseInt(sideWidth);
    if (tab !== null) this.tab = tab;
    if (order !== null) this.order = order;

    this.dataset.id = parseInt(this.identifier);
    // coming from the import dialog on the datasets page: follow its task
    if (this.$route.query.importTask) {
      this.importing.id = parseInt(this.$route.query.importTask);
      this.pollImportTask();
    }
    this.updatePage();
  },
  mounted() {
    window.addEventListener("mouseup", this.stopDrag);
    window.addEventListener("mousedown", this.startDrag);
  },
  unmounted() {
    clearTimeout(this.importPoll);
    window.removeEventListener("mouseup", this.stopDrag);
    window.removeEventListener("mousedown", this.startDrag);
  }
};
</script>

<style scoped>
.breadcrumb {
  padding: 0px;
  margin: 5px 0;
}

.btn-link {
  padding: 0px;
}

.sidebar .title {
  color: white;
}

.progress {
  padding: 2px;
  height: 24px;
}

.sidebar {
  height: 100%;
  position: fixed;
  color: white;
  z-index: 1;
  top: 0;
  left: 0;
  background-color: #4b5162;
  overflow-x: hidden;
  padding-top: 60px;
}

.sidebar .closebtn {
  position: absolute;
  top: 0;
  right: 25px;
  font-size: 36px;
  margin-left: 50px;
}

.sidebar-title {
  color: white;
}

.sidebar-section-buttons {
  margin: 5px;
}

.sidebar-section {
  margin: 5px;
  border-radius: 5px;
  background-color: #383c4a;
  padding: 0 5px 2px 5px;
  overflow: auto;
}

.exports-tab {
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 24px;
}
.export-table td,
.export-table th {
  padding: 0.6rem 0.75rem;
}

.export-steps {
  display: flex;
  list-style: none;
  padding: 0;
  margin: 0 0 1rem;
  counter-reset: step;
}
.export-steps li {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  position: relative;
  cursor: pointer;
  color: #6c757d;
  font-size: 0.85rem;
}
.export-steps li.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.export-steps li:not(:last-child)::after {
  content: "";
  position: absolute;
  top: 15px;
  left: calc(50% + 20px);
  right: calc(-50% + 20px);
  height: 2px;
  background: #dee2e6;
}
.export-steps li.done:not(:last-child)::after {
  background: #198754;
}
.export-steps .step-dot {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 2px solid #ced4da;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}
.export-steps li.active {
  color: #0d6efd;
  font-weight: 600;
}
.export-steps li.active .step-dot {
  border-color: #0d6efd;
  background: #0d6efd;
  color: #fff;
}
.export-steps li.done .step-dot {
  border-color: #198754;
  background: #198754;
  color: #fff;
}
.choice-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  height: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid #dee2e6;
  border-radius: 0.5rem;
  cursor: pointer;
  margin: 0;
}
.choice-card:hover {
  border-color: #86b7fe;
}
.choice-card.selected {
  border-color: #0d6efd;
  box-shadow: 0 0 0 1px #0d6efd;
  background: rgba(13, 110, 253, 0.05);
}
.export-summary {
  background: #f8f9fa;
  border-radius: 0.5rem;
  padding: 0.6rem 0.75rem;
}
.zip-tree {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 0.375rem;
  padding: 0.5rem 0.75rem;
  white-space: pre;
  overflow-x: auto;
}
.export-steps li.skipped .step-dot {
  border-style: dashed;
  color: #adb5bd;
}
.export-steps li.skipped {
  opacity: 0.5;
}
</style>
