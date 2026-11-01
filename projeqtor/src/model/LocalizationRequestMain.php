<?php

require_once('_securityCheck.php');
class LocalizationRequestMain extends SqlElement
{
    public $_sec_description;
    public $id;    // redefine $id to specify its visible place
    public $name;
    public $localizationId;
    public $idProductVersion;
    public $idComponentVersion;
    public $idActivity;
    public $idLocalizationRequestType;
    public $idLocalizationItemType;
    public $idStatus;
    public $idle;
    public $idResource;
    public $idAccountable;
    public $plannedDeliveryDate;
    public $realDeliveryDate;
    public $_sec_contextLocalization;
    public $context;
    public $_sec_textToTranslate;
    public $idLanguage;
    public $textToTranslate;
    public $_sec_linkedLocalizationItems;
    public $_localizationItem;
    public $creationDateTime;
    public $_sec_Link;
    public $_Link = array();
    public $_Attachment=array();
    public $_Note=array();

    private static $_layout='
    <th field="id" formatter="numericFormatter" width="15%"># ${id}</th>
    <th field="name" width="75%">${name}</th>
    <th field="idle" width="10%" formatter="booleanFormatter">${idle}</th>
    ';



    private static $_fieldsAttributes=array(
        "id"=>"",
        "name"=>"required",
        "idStatus"=>"required",
        "idLanguage"=>"required",
        "idLocalizationRequestType"=>"required",
        "idLocalizationItemType"=>"required"
    );

    private static $_colCaptionTransposition = array(
        'idResource'=> 'responsible',
        'context'=>'idContext',
        'idLanguage'=>'idOriginLanguage'
    );

    /**
     * LocalizationTranslatorMain constructor.
     * @param $_sec_description
     */
    public function __construct($id = NULL, $withoutDependentObjects=false)
    {
        parent::__construct($id,$withoutDependentObjects);
        if ($withoutDependentObjects) return;


    }

    /** ==========================================================================
     * Destructor
     * @return void
     */
    public function __destruct() {
        parent::__destruct();
    }

// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********

    /** ==========================================================================
     * Return the specific layout
     * @return String the layout
     */
    protected function getStaticLayout() {
        return self::$_layout;
    }

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


    public function control(){
        $result="";
        $old = $this->getOld();

        if ($this->idComponentVersion and $this->idProductVersion) {
            $result.='<br/>' . i18n('componentVersionOrProductVersion');
        }
        else if (!$this->idComponentVersion and !$this->idProductVersion){
            $result.='<br/>' . i18n('specifiedComponentVersionOrProductVersion');
        }
        else if ($this->idComponentVersion){
            $versionLanguage = new VersionLanguage();
            $countLanguage = $versionLanguage->countSqlElementsFromCriteria(array("idVersion"=>$this->idComponentVersion));
            if ($countLanguage == 0){
                $result.='<br/>' . i18n('noLanguageInComponentVersion');
            }
        }
        else if ($this->idProductVersion){
            $versionLanguage = new VersionLanguage();
            $countLanguage = $versionLanguage->countSqlElementsFromCriteria(array("idVersion"=>$this->idProductVersion));
            if ($countLanguage == 0){
                $result.='<br/>' . i18n('noLanguageInProductVersion');
            }
        }
        else if ($this->idComponentVersion =! $old->idComponentVersion or $this->idProductVersion != $old->idProductVersion){
            $localizationItem = new LocalizationItem();
            $cpt = $localizationItem->countSqlElementsFromCriteria(array("idLocalizationRequest"=> $this->id));
            if ($cpt > 0){
                $result.='<br/>' . i18n('localizationItemAlreadyCreated');
            }
        }

        if ($this->idLocalizationItemType != $old->idLocalizationItemType){
            $localizationItem = new LocalizationItem();
            $cpt = $localizationItem->countSqlElementsFromCriteria(array("idLocalizationRequest"=> $this->id));
            if ($cpt > 0){
                $result.='<br/>' . i18n('noChangeItemTypeLocalizationItemAlreadyCreated');
            }
        }


        if ($result == "") {
            $result = 'OK';
        }
        return $result;
    }


    public function save()
    {
        $old = $this->getOld();
        $isCreated = 0;
        if (!$this->plannedDeliveryDate){
            $this->plannedDeliveryDate = date('Y-m-d');
            $type = new LocalizationRequestType($this->idLocalizationRequestType);
            $numberDaysBeforeDuedate = $type->numberDaysBeforeDueDate;
            $this->plannedDeliveryDate = $date = date('Y-m-d', pq_strtotime("+" . $numberDaysBeforeDuedate . " days"));
        }

        $result=parent::save();
        if ($old->idStatus != $this->idStatus){
            $localizationRequestType = new LocalizationRequestType($this->idLocalizationRequestType);
            if ($this->idStatus == $localizationRequestType->idStatus){
                $isCreated = $this->generateItemsOnchangeStatus();
            }
        }
        if ($isCreated == 0){ // Do not update if it's just after creation
            $this->updateItems();
        }

        return $result;
    }



    public function updateItems(){
        $localizationItem = new LocalizationItem();
        $listLocalizationItem = $localizationItem->getSqlElementsFromCriteria(array("idLocalizationRequest"=>$this->id));

        foreach ($listLocalizationItem as $localizationItem){
            if ($this->plannedDeliveryDate){
                $localizationItem->actualDueDate = $this->plannedDeliveryDate;
            }
            else if($this->realDeliveryDate){
                $localizationItem->actualDueDate = $this->realDeliveryDate;
            }
            $localizationItem->context = $this->context;
            $languageName = SqlList::getNameFromId("Language", $localizationItem->idLanguage);
            $localizationItem->name = $this->name . ' - ' . $languageName;
            $localizationItem->idResource = $this->idResource;
            $localizationItem->localizationId = $this->localizationId;
            $localizationItem->save();
        }
    }


    public function generateItemsOnchangeStatus(){
        $idVersion = null;
        if ($this->idProductVersion){
            $idVersion = $this->idProductVersion;
        }
        elseif($this->idComponentVersion){
            $idVersion = $this->idComponentVersion;
        }
        else{
            // ("do not generate because no component version or no product version");
        }
        $versionLanguage = new VersionLanguage();
        $listLang = array();

        if ($idVersion){
            $listLang = $versionLanguage->getSqlElementsFromCriteria(array("idVersion"=>$idVersion));
        }

        $tit = new LocalizationItemType($this->idLocalizationItemType);
        $wf = new Workflow($tit->idWorkflow);
        if ($tit->idStatus){
            $idStatus = $tit->idStatus;
        }
        else{
            $lstStatus = $wf->getWorkflowStatusList();
            $idStatus = $lstStatus[0]->id;
        }

        $originLanguage = $this->idLanguage;
        $isCreated = 0;
        foreach($listLang as $lang){
            if ($originLanguage and $lang->idLanguage != $originLanguage) { // if origin language exists, do not generate translation item for this language.
                $localizationItem = new LocalizationItem();
                $listLocalizationItemExists = $localizationItem->countSqlElementsFromCriteria(array("idLocalizationRequest" => $this->id, "idLanguage" => $lang->idLanguage));

                if ($listLocalizationItemExists == 0) {
                    $languageName = SqlList::getNameFromId("Language", $lang->idLanguage);
                    $localizationItem->name = $this->name . ' - ' . $languageName;
                    $localizationItem->idLanguage = $lang->idLanguage;
                    $localizationItem->idLocalizationItemType = $this->idLocalizationItemType;
                    $localizationItem->idLocalizationRequest = $this->id;
                    $localizationItem->idOriginLanguage = $this->idLanguage;
                    $localizationItem->textToTranslate = $this->textToTranslate;
                    $localizationItem->idStatus = $idStatus;
                    $localizationItem->idResource = $this->idResource;
                    $localizationItem->localizationId = $this->localizationId;
                    $localizationItem->context = $this->context;
                    if ($this->plannedDeliveryDate){
                        $localizationItem->actualDueDate = $this->plannedDeliveryDate;
                    }
                    else if($this->realDeliveryDate){
                        $localizationItem->actualDueDate = $this->realDeliveryDate;
                    }

                    if ($this->idProductVersion) {
                        $localizationItem->idProductVersion = $this->idProductVersion;
                    } elseif ($this->idComponentVersion) {
                        $localizationItem->idComponentVersion = $this->idComponentVersion;
                    }
                    $isCreated++;
                    $localizationItem->save();
                }
            }
        }

        return $isCreated;
    }


}