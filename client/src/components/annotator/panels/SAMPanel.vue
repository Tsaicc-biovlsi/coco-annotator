<template>
  <div v-show="sam.isActive">
    <PanelText :name="sam.statusText" />
    <PanelButton name="Apply (Enter)" @click="sam.apply()" />
    <PanelButton name="Undo Last Prompt" @click="sam.undoPoint()" />
    <PanelButton name="Clear Prompts" @click="sam.reset()" />
    <PanelToggle name="Replace Annotation" v-model:value="sam.settings.replace" />
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
