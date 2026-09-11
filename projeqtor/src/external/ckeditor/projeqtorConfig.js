/**
 * @license Copyright (c) 2003-2015, CKSource - Frederico Knabben. All rights reserved.
 * For licensing, see LICENSE.md or http://ckeditor.com/license
 */

CKEDITOR.editorConfig = function( config ) {
  config.toolbar = [
    { name: 'basicstyles', items: [ 'Bold', 'Italic', 'Underline', '-', 'CopyFormatting','RemoveFormat'] },
    { name: 'paragraph', items: [ 'Indent', 'Outdent', '-', 'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock','-','NumberedList', 'BulletedList'] },
    { name: 'colors', items: [ 'TextColor', 'BGColor' ] },
    { name: 'tools', items: [ 'Replace','Print','Maximize','ProjeqtorFullscreen'] },
    { name: 'styles', items: [ 'Font', 'FontSize' ] },
    { name: 'links', items: [ 'Link', 'Unlink', 'Image','Table','Blockquote','Smiley','SpecialChar','PasteFromWord','Source'] }
  ];
  // 'showBlocks'
  config.enterMode = CKEDITOR.ENTER_DIV;
  //config.enterMode = CKEDITOR.ENTER_BR;
  config.removeDialogTabs = 'link:advanced;image:advanced;image:link';
  config.removePlugins='magicline';
  config.uploadUrl = '../tool/uploadImage.php?csrfToken='+parent.csrfToken;
  config.imageUploadUrl = '../tool/uploadImage.php?csrfToken='+parent.csrfToken;
  config.image_previewText = CKEDITOR.tools.repeat( 'Image', 1 );
  config.magicline_color = '#aaaaaa';
  config.extraAllowedContent = 'span(*){*};span(pqMentionLink)[contenteditable,data-mention-class,data-mention-id,data-mention-name];div(*){*};p(*){*};table(*){*};tr(*){*};td(*){*};pre(*){*};blockquote(*){*};br[clear];style;';
  config.pasteFilter='span(*){*};span(pqMentionLink)[contenteditable,data-mention-class,data-mention-id,data-mention-name];div(*){*};p(*){*};table(*){*};tr(*){*};td(*){*};pre(*){*};blockquote(*){*};br[clear];style';
  // Inject mention CSS into the editor iframe so .pqMentionLink keeps its color/weight inside CKEditor
  config.contentsCss = [CKEDITOR.getUrl('contents.css'), CKEDITOR.getUrl('pqMention.css')];
  config.resize_minHeight = 150;
  config.extraPlugins = 'openlink';
  config.extraPlugins += ',sourcearea';
  //config.extraPlugins += ',image2';
  //config.extraPlugins += ',uploadimage';
  //gautier
  if (dojo.byId('ckeditorType')){
    var cktype=dojo.byId('ckeditorType').value;
    if ((cktype != 'CK' && ! currentEditorIsNote) || forceCkInline) {
      config.removeButtons = 'tools,Maximize';
      config.extraPlugins += ',staticspace';
      config.staticSpacePriority=1;
      if (! forceCkInline) config.extraPlugins+=',projeqtorfullscreen';
      //config.staticSpacePositionY='bottom';
      //config.staticSpacePositionX='left';
      if (forceCkInline) config.removePlugins += ',elementspath';
      if (forceCkInline) config.resize_enabled = false;
    }
  }
  //config.removePlugins+=',language,liststyle,tableselection,tabletools,scayt,contextmenu,openlink';
  //config.pasteFromWordRemoveStyles = false; // Removed in 4.6.0
  //config.pasteFromWordRemoveFontStyles = false; // Deprecated in 4.6.0, defaults to false
  config.scayt_sLang = getLocalLocation();
  config.scayt_autoStartup = getLocalScaytAutoStartup();
  config.disableNativeSpellChecker = false;
};

//CKEDITOR.on('instanceReady', function(ck) { ck.editor.removeMenuItem('paste');});

// Install mention tooltip delegation inside the CKEditor iframe (parent listeners don't reach iframe docs)
if (!CKEDITOR._pqMentionHookInstalled) {
  CKEDITOR._pqMentionHookInstalled = true;
  CKEDITOR.on('instanceReady', function(ev) {
    var editor = ev.editor;
    try {
      // Inline editors live in the parent DOM => already covered by document delegation
      if (editor.editable && editor.editable() && editor.editable().isInline && editor.editable().isInline()) return;
    } catch(e) {}
    if (!editor.document || !editor.document.$) return;
    var doc = editor.document.$;
    var win = window;
    // Propage --color-secondary (and a few other useful settings) from the parent page to
    // the iframe so that .pqMentionLink uses the user's theme color.
    try {
      var parentVarSource = (win.document.getElementById('body')) || win.document.body || win.document.documentElement;
      if (parentVarSource && doc.documentElement) {
        var varsToCopy = ['--color-secondary','--color-darker-secondary','--color-dark-secondary'];
        var cs = win.getComputedStyle(parentVarSource);
        for (var i=0; i<varsToCopy.length; i++) {
          var v = cs.getPropertyValue(varsToCopy[i]);
          if (v && v.trim()) doc.documentElement.style.setProperty(varsToCopy[i], v.trim());
        }
      }
    } catch(e) {}
    var closest = function(n) {
      while (n && n !== doc) {
        if (n.classList && n.classList.contains('pqMentionLink')) return n;
        n = n.parentNode;
      }
      return null;
    };
    var getIframeOffset = function() {
      try {
        var iframe = editor.window && editor.window.getFrame && editor.window.getFrame().$;
        if (!iframe) return {top:0,left:0};
        var r = iframe.getBoundingClientRect();
        return {top:r.top, left:r.left};
      } catch(e) { return {top:0,left:0}; }
    };
    doc.addEventListener('mouseover', function(e) {
      var span = closest(e.target);
      if (!span) return;
      if (typeof win.showMentionTooltip === 'function') {
        win.showMentionTooltip(span, getIframeOffset());
      }
    }, true);
    doc.addEventListener('mouseout', function(e) {
      var span = closest(e.target);
      if (!span) return;
      var related = e.relatedTarget;
      if (related && span.contains(related)) return;
      // If you click directly on another entry in the iframe, the next mouseover event handles
      if (related && closest(related)) return;
      if (typeof win.hideMentionTooltip === 'function') {
        win.hideMentionTooltip();
      }
    }, true);
    // Hide on scroll inside the editor iframe
    if (editor.window && editor.window.$) {
      editor.window.$.addEventListener('scroll', function() {
        if (typeof win.hideMentionTooltip === 'function') win.hideMentionTooltip();
      }, true);
    }
  });
}

