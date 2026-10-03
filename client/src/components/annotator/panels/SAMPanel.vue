<template>
  <div v-show="sam.isActive">
    <PanelText :name="sam.statusText" />
    <PanelButton :name="$t('sAMPanel.applyEnter')" @click="sam.apply()" />
    <PanelButton :name="$t('sAMPanel.undoLastPrompt')" @click="sam.undoPoint()" />
    <PanelButton :name="$t('sAMPanel.clearPrompts')" @click="sam.reset()" />
    <PanelToggle :name="$t('sAMPanel.replaceAnnotation')" v-model:value="sam.settings.replace" />
  </div>
</template>

<script>
import PanelButton from "@/components/PanelButton.vue";
import PanelText from "@/components/PanelText.vue";
import PanelToggle from "@/components/PanelToggle.vue";

export default {
  name: "SAMPanel",
  components: { PanelButton, PanelText, PanelToggle },
  props: {
    sam: {
      type: Object,
      required: true
    }
  }
};
</script>
