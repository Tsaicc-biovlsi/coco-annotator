<template>
  <div v-show="rbbox.isActive">
    <PanelText :name="rbbox.hint" />
    <PanelText v-if="rbbox.box && !rbbox.drawing" name="Arrow keys: move 1 px (Shift: 10 px)" />
    <PanelButton name="Rotate −5°" @click="rbbox.rotateBy(-5)" />
    <PanelButton name="Rotate +5°" @click="rbbox.rotateBy(5)" />
    <PanelButton name="Swap Heading (90°)" @click="rbbox.swapHeading()" />
    <PanelInputNumber
      name="Shift Snap (°)"
      min="0"
      max="90"
      step="5"
      v-model:value="rbbox.settings.snap"
    />
    <PanelInputString name="Handle Color" v-model:value="rbbox.settings.strokeColor" />
  </div>
</template>

<script>
import PanelButton from "@/components/PanelButton.vue";
import PanelText from "@/components/PanelText.vue";
import PanelInputNumber from "@/components/PanelInputNumber.vue";
import PanelInputString from "@/components/PanelInputString.vue";

export default {
  name: "RotatedBBoxPanel",
  components: { PanelButton, PanelText, PanelInputNumber, PanelInputString },
  props: {
    rbbox: {
      type: Object,
      required: true
    }
  }
};
</script>
