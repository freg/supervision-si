<?php


class LocalizationItemMain extends SqlElement
{
    public $_sec_description;
    public $id;    // redefine $id to specify its visible place
    public $name;
    public $localizationId;
    public $idLocalizationItemType;
    public $idLocalizationRequest;
    public $idProductVersion;
    public $idComponentVersion;
    public $idOriginLanguage;
    public $idLanguage;
    public $idStatus;
    public $idResource;
    public $idLocalizationTranslator;
    public $textToTranslate;
    public $idle;
    public $_sec_contextLocalization;
    public $context;
    public $_sec_treatment;
    public $actualDueDate;
    public $automaticProcess;
    public $localizationResult;
    public $_Attachment=array();
    public $_Note=array();

    private static $_fieldsAttributes=array(
        "id"=>"",
        "name"=>"required,readonly",
        "idLocalizationRequest"=>"required,readonly",
        "idStatus"=>"required",
        "idResource"=>"readonly",
        "idProductVersion"=>"readonly",
        "idComponentVersion"=>"readonly",
        "idLanguage"=>"required,readonly",
        "idOriginLanguage"=>"required,readonly",
        "actualDueDate"=>"readonly",
        "localizationId"=>"readonly",
        "context"=>"readonly",
        "textToTranslate"=>"readonly",
        "idLocalizationItemType"=>"readonly",
        "idle"=>"nobr"
    );

    public function __construct($id = NULL, $withoutDependentObjects=false)
    {
      parent::__construct($id,$withoutDependentObjects);
      if ($withoutDependentObjects) return;
    }
    
    public function __destruct() {
      parent::__destruct();
    }
    
    private static $_colCaptionTransposition = array(
        'context'=>'idContext',
        'idResource'=>'responsible'
    );

    /** ==========================================================================
     * Return the specific fieldsAttributes
     * @return Array the fieldsAttributes  
     */
    protected function getStaticFieldsAttributes() {
        return self::$_fieldsAttributes;
    }

    /** ============================================================================
     * Return the specific colCaptionTransposition
     * @return String the colCaptionTransposition
     */
    protected function getStaticColCaptionTransposition($fld=null) {
        return self::$_colCaptionTransposition;
    }


}